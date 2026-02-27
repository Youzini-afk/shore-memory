use chacha20poly1305::{
    aead::{Aead, KeyInit},
    XChaCha20Poly1305, XNonce,
};
use hkdf::Hkdf;
use napi::{Error, Result, Status};
use obfstr::obfstr;
use sha2::Sha256;

// ========== .pero v2 文件格式定义 ==========
// | 偏移量 | 长度 | 字段      | 描述                        |
// |--------|------|-----------|----------------------------|
// | 0      | 4    | Magic     | "PERO" 魔数                |
// | 4      | 2    | Version   | 文件格式版本 (u16 LE)      |
// | 6      | 4    | MetaLen   | 元数据长度 (u32 LE)        |
// | 10     | N    | Metadata  | JSON 格式的元数据          |
// | 10+N   | 32   | Salt      | HKDF salt                  |
// | 42+N   | 24   | Nonce     | XChaCha20 Nonce            |
// | 66+N   | M    | Ciphertext| 加密数据 (含 Poly1305 Tag) |
//
// 版本号 → 算法映射（内部逻辑，不对外暴露）:
// v1: XChaCha20-Poly1305 (旧格式，已废弃)
// v2: HKDF-SHA256 + XChaCha20-Poly1305 + 魔改XOR

const PERO_MAGIC: &[u8; 4] = b"PERO";
const PERO_VERSION_V2: u16 = 2;
const HEADER_SIZE_V2: usize = 10; // Magic(4) + Version(2) + MetaLen(4)
const SALT_SIZE: usize = 32;
const NONCE_SIZE: usize = 24;

/// 使用 HKDF-SHA256 派生会话密钥
fn derive_key(salt: &[u8]) -> Result<[u8; 32]> {
    // 密钥下放：主密钥不再从外部传入，而是隐藏在 Rust 内部
    let master_key = obfstr::obfbytes!(b"\xdb\x05\x5e\x7f\x6c\xc0\xfd\xf9\x3a\x1a\x34\x20\x99\x5b\x1e\x41\xa2\x04\xe6\x0e\x81\xed\x7f\x5f\xb5\x8f\x88\x02\x3b\x13\xce\xa2");
    
    let hkdf = Hkdf::<Sha256>::new(Some(salt), master_key);
    let mut derived_key = [0u8; 32];
    hkdf.expand(b"PERO_MODEL_ENCRYPTION_KEY_V2", &mut derived_key)
        .map_err(|_| Error::new(Status::GenericFailure, "HKDF 密钥派生失败".to_string()))?;
    Ok(derived_key)
}

/// 解密 .pero v2 格式的数据
/// 内部版本：使用硬编码的内部密钥
pub fn decrypt_pero_data_secure(encrypted_data: &[u8]) -> Result<Vec<u8>> {
    // 最小文件大小: Header(10) + Salt(32) + Nonce(24) + Poly1305Tag(16) = 82
    if encrypted_data.len() < HEADER_SIZE_V2 + SALT_SIZE + NONCE_SIZE + 16 {
        return Err(Error::new(
            Status::InvalidArg,
            obfstr!("数据太小").to_string(),
        ));
    }

    // 1. 验证 Magic Number
    if &encrypted_data[0..4] != PERO_MAGIC {
        return Err(Error::new(
            Status::InvalidArg,
            obfstr!("无效的文件格式").to_string(),
        ));
    }

    // 2. 解析头部
    let version = u16::from_le_bytes([encrypted_data[4], encrypted_data[5]]);
    let meta_len = u32::from_le_bytes([
        encrypted_data[6],
        encrypted_data[7],
        encrypted_data[8],
        encrypted_data[9],
    ]) as usize;

    // 3. 验证版本（仅支持 v2）
    if version != PERO_VERSION_V2 {
        return Err(Error::new(
            Status::InvalidArg,
            obfstr!("不支持的文件版本").to_string(),
        ));
    }

    // 4. 定位加密数据起始位置
    let crypto_start = HEADER_SIZE_V2 + meta_len;
    if encrypted_data.len() < crypto_start + SALT_SIZE + NONCE_SIZE {
        return Err(Error::new(
            Status::InvalidArg,
            obfstr!("文件损坏").to_string(),
        ));
    }

    // 5. 提取 Salt, Nonce, Ciphertext
    let salt = &encrypted_data[crypto_start..crypto_start + SALT_SIZE];
    let nonce = XNonce::from_slice(
        &encrypted_data[crypto_start + SALT_SIZE..crypto_start + SALT_SIZE + NONCE_SIZE],
    );
    let mut ciphertext = encrypted_data[crypto_start + SALT_SIZE + NONCE_SIZE..].to_vec();

    // 6. 使用 HKDF 派生会话密钥 (内部获取 Master Key)
    let derived_key = derive_key(salt)?;

    // 7. "魔改" 逆变换
    let magic_pattern = obfstr::obfbytes!(b"PERO_CORE_MAGIC_PATTERN_2026");
    for (i, byte) in ciphertext.iter_mut().take(magic_pattern.len()).enumerate() {
        *byte ^= magic_pattern[i];
    }

    // 8. AEAD 解密
    let cipher = XChaCha20Poly1305::new_from_slice(&derived_key)
        .map_err(|_| Error::new(Status::InvalidArg, obfstr!("无效的密钥长度").to_string()))?;

    cipher
        .decrypt(nonce, ciphertext.as_ref())
        .map_err(|_| Error::new(Status::GenericFailure, obfstr!("解密失败").to_string()))
}
