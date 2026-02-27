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

use std::time::Instant;
#[cfg(target_os = "windows")]
use windows::Win32::System::Diagnostics::Debug::{CheckRemoteDebuggerPresent, IsDebuggerPresent};
#[cfg(target_os = "windows")]
use windows::Win32::System::Threading::GetCurrentProcess;

/// 多重反调试检查
/// 返回 true 如果检测到调试器
fn is_debugger_detected() -> bool {
    #[cfg(target_os = "windows")]
    unsafe {
        // 1. 基础检查: IsDebuggerPresent
        if IsDebuggerPresent().as_bool() {
            return true;
        }

        // 2. 远程调试检查: CheckRemoteDebuggerPresent
        let mut is_remote_present = false.into();
        let _ = CheckRemoteDebuggerPresent(GetCurrentProcess(), &mut is_remote_present);
        if is_remote_present.as_bool() {
            return true;
        }

        // 3. 时间差检查: 检测单步执行 (rdtsc 类似逻辑)
        // 在解密这种关键操作中，如果耗时异常巨大，极可能是被单步跟踪
        let start = Instant::now();
        // 执行一段极短但无法被完全优化的逻辑
        let mut sink = 0u64;
        for i in 0..100 {
            sink = sink.wrapping_add(i);
        }
        std::hint::black_box(sink);

        if start.elapsed().as_micros() > 500 {
            // 100次加法不可能超过500微秒，除非在调试
            return true;
        }
    }
    false
}

/// 虚假密钥组装：看起来很像真的，但产生的是垃圾数据，用于迷惑分析喵
#[inline(never)]
fn assemble_decoy_key() -> [u8; 32] {
    let mut key = [0u8; 32];
    let d1 = obfstr::obfbytes!(b"\x12\x34\x56\x78\x90\xAB\xCD\xEF");
    let d2 = obfstr::obfbytes!(b"\xFE\xDC\xBA\x09\x87\x65\x43\x21");
    for i in 0..16 {
        key[i] = d1[i % 8] ^ 0xAA;
        key[i + 16] = d2[i % 8] ^ 0x55;
    }
    key
}

/// 密钥碎片化与动态异或组装
fn assemble_master_key() -> [u8; 32] {
    let mut key = [0u8; 32];

    // 密钥碎片 (XOR 掩码后的密文)
    let p1 = obfstr::obfbytes!(b"\xdb\x05\x5e\x7f\x6c\xc0\xfd\xf9");
    let p2 = obfstr::obfbytes!(b"\x3a\x1a\x34\x20\x99\x5b\x1e\x41");
    let p3 = obfstr::obfbytes!(b"\xa2\x04\xe6\x0e\x81\xed\x7f\x5f");
    let p4 = obfstr::obfbytes!(b"\xb5\x8f\x88\x02\x3b\x13\xce\xa2");

    // 动态掩码 (为了不让真实的 p1-p4 在静态分析中显得太突兀，我们增加一个运行时层)
    let mask = obfstr::obfbytes!(b"PERO_DYNAMIC_XOR_MASK_2026");

    for i in 0..8 {
        // 这里的异或逻辑是透明的（目前掩码实际上并不改变数据，只是为了增加指令复杂度）
        // 真正的加固在于：破解者在静态分析时，看到的逻辑是：
        // key[i] = (p1[i] ^ mask[i]) ^ mask[i]
        // 这会多出数十条汇编指令，极大地增加了分析成本喵！
        key[i] = (p1[i] ^ mask[i % mask.len()]) ^ mask[i % mask.len()];
        key[i + 8] = (p2[i] ^ mask[(i + 8) % mask.len()]) ^ mask[(i + 8) % mask.len()];
        key[i + 16] = (p3[i] ^ mask[(i + 16) % mask.len()]) ^ mask[(i + 16) % mask.len()];
        key[i + 24] = (p4[i] ^ mask[(i + 24) % mask.len()]) ^ mask[(i + 24) % mask.len()];
    }

    key
}

/// 使用 HKDF-SHA256 派生会话密钥
fn derive_key(salt: &[u8]) -> Result<[u8; 32]> {
    // 1. 动态检测调试环境
    if is_debugger_detected() {
        // 如果检测到调试器，不直接退出，而是返回一个虚假的派生密钥
        // 攻击者会拿到错误的解密结果，但无法直接定位到反调试逻辑喵！
        return Ok(assemble_decoy_key());
    }

    // 迷惑路径：调用虚假组装，但不使用其结果
    let _decoy = assemble_decoy_key();

    // 真正的密钥下放
    let mut master_key = assemble_master_key();

    let hkdf = Hkdf::<Sha256>::new(Some(salt), &master_key);
    let mut derived_key = [0u8; 32];
    let res = hkdf.expand(b"PERO_MODEL_ENCRYPTION_KEY_V2", &mut derived_key);

    // 关键点：使用完主密钥后，立即从栈上“擦除”它
    // 这样内存中完整密钥的存在时间只有微秒级喵！
    for b in master_key.iter_mut() {
        *b = 0x00;
    }

    res.map_err(|_| Error::new(Status::GenericFailure, "HKDF 密钥派生失败".to_string()))?;
    Ok(derived_key)
}

/// 解密 .pero v2 格式的数据
/// 内部版本：使用硬编码的内部密钥
fn decrypt_pero_v2(encrypted_data: &[u8]) -> Result<Vec<u8>> {
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

const INV_SBOX1: [u8; 256] = [
    190, 150, 126, 12, 162, 187, 33, 226, 241, 53, 78, 26, 158, 161, 56, 40, 73, 135, 141, 238,
    131, 7, 176, 50, 67, 142, 121, 184, 55, 9, 46, 174, 75, 173, 206, 188, 168, 85, 160, 107, 217,
    89, 166, 227, 23, 34, 106, 48, 243, 97, 249, 31, 194, 44, 147, 108, 246, 122, 203, 113, 22,
    221, 144, 16, 207, 1, 83, 233, 205, 77, 247, 178, 183, 90, 204, 177, 202, 36, 118, 252, 157,
    244, 136, 229, 76, 5, 139, 51, 145, 159, 215, 130, 92, 10, 143, 179, 94, 87, 200, 248, 196, 28,
    222, 115, 71, 242, 210, 100, 29, 6, 69, 169, 231, 172, 189, 138, 208, 3, 129, 21, 109, 38, 86,
    24, 102, 43, 96, 103, 154, 151, 195, 25, 236, 228, 111, 30, 146, 65, 47, 37, 68, 212, 79, 216,
    0, 95, 201, 66, 45, 239, 255, 27, 128, 93, 127, 99, 35, 104, 98, 15, 163, 253, 186, 41, 211,
    193, 209, 180, 181, 52, 225, 140, 61, 112, 116, 254, 237, 235, 185, 220, 123, 114, 81, 192, 59,
    155, 42, 182, 156, 17, 58, 62, 250, 82, 152, 101, 57, 218, 232, 137, 175, 60, 84, 234, 80, 19,
    14, 125, 110, 132, 219, 119, 64, 63, 134, 191, 224, 91, 39, 74, 4, 214, 88, 117, 170, 2, 124,
    32, 165, 70, 230, 199, 120, 149, 198, 148, 49, 171, 164, 197, 153, 8, 251, 18, 245, 11, 167,
    105, 223, 20, 13, 72, 133, 213, 240, 54,
];
const INV_SBOX2: [u8; 256] = [
    114, 177, 143, 77, 8, 45, 255, 135, 63, 211, 1, 111, 251, 97, 86, 167, 90, 123, 113, 41, 132,
    96, 217, 69, 205, 194, 134, 201, 53, 118, 191, 164, 44, 151, 156, 239, 13, 231, 148, 116, 168,
    40, 52, 224, 238, 87, 198, 75, 28, 185, 94, 25, 230, 253, 208, 67, 32, 186, 226, 204, 55, 56,
    14, 182, 243, 197, 128, 173, 62, 48, 19, 172, 82, 140, 249, 81, 241, 248, 57, 104, 51, 117,
    252, 233, 107, 15, 170, 195, 92, 36, 174, 193, 184, 3, 166, 237, 228, 109, 42, 162, 38, 34,
    190, 119, 43, 131, 196, 136, 30, 223, 20, 72, 161, 245, 35, 227, 180, 130, 22, 91, 121, 6, 221,
    78, 5, 76, 229, 61, 102, 124, 108, 127, 115, 70, 27, 84, 247, 222, 240, 137, 215, 250, 95, 37,
    200, 142, 29, 110, 218, 181, 54, 232, 105, 23, 83, 2, 147, 216, 246, 188, 153, 93, 39, 155,
    169, 236, 47, 133, 187, 49, 242, 24, 126, 7, 225, 10, 17, 206, 79, 100, 178, 59, 73, 58, 189,
    159, 4, 98, 120, 220, 203, 99, 219, 145, 149, 146, 50, 210, 207, 71, 66, 74, 106, 209, 65, 214,
    150, 160, 89, 163, 11, 101, 235, 16, 141, 157, 213, 202, 175, 103, 68, 26, 129, 144, 85, 152,
    125, 171, 154, 234, 88, 31, 183, 192, 199, 33, 139, 21, 64, 18, 46, 212, 60, 176, 165, 112,
    254, 80, 122, 0, 158, 9, 138, 12, 244, 179,
];
/// 轮密钥碎片化获取函数
/// 杜绝内存中出现完整的 "PERO_WBC_SPN_26" 字符串
#[inline(always)]
fn get_wbc_key_byte(i: usize) -> u8 {
    let idx = i % 15;
    if idx < 4 {
        obfstr::obfbytes!(b"PERO")[idx]
    } else if idx < 8 {
        obfstr::obfbytes!(b"_WBC")[idx - 4]
    } else if idx < 12 {
        obfstr::obfbytes!(b"_SPN")[idx - 8]
    } else {
        obfstr::obfbytes!(b"_26")[idx - 12]
    }
}

/// 自定义微型虚拟机指令集 (OpCodes)
/// 使用随机分配的数值增加逆向难度
const OP_LOAD: u8 = 0x1A; // 加载字节
const OP_SBOX1: u8 = 0x2B; // 逆置换1
const OP_SBOX2: u8 = 0x3C; // 逆置换2
const OP_XOR: u8 = 0x4D; // 轮密钥异或
const OP_STORE: u8 = 0x5E; // 存储字节
const OP_EXIT: u8 = 0xFF; // 退出
const OP_NOP: u8 = 0x90; // 空指令 (垃圾指令)

/// 应用白盒逆向转换 (通过自定义微型虚拟机执行)
/// 这种方式彻底隐藏了加解密的逻辑流，攻击者只能看到一系列跳转和状态切换
fn apply_wbc_inverse(data: &mut [u8]) {
    // 预定义的字节码序列：Load -> Sbox2 -> Xor -> Sbox1 -> Store
    // 为了增加难度，我们在其中穿插了大量的 NOP 垃圾指令
    let bytecode: [u8; 12] = [
        OP_LOAD, OP_NOP, OP_SBOX2, OP_NOP, OP_XOR, OP_NOP, OP_NOP, OP_SBOX1, OP_STORE, OP_NOP,
        OP_EXIT, 0x00, // 填充
    ];

    for (i, byte) in data.iter_mut().enumerate() {
        let mut reg: u8 = 0; // 虚拟寄存器
        let mut pc: usize = 0; // 虚拟程序计数器

        loop {
            let op = bytecode[pc];
            match op {
                OP_LOAD => {
                    reg = *byte;
                    pc += 1;
                }
                OP_SBOX1 => {
                    reg = INV_SBOX1[reg as usize];
                    pc += 1;
                }
                OP_SBOX2 => {
                    reg = INV_SBOX2[reg as usize];
                    pc += 1;
                }
                OP_XOR => {
                    reg ^= get_wbc_key_byte(i);
                    pc += 1;
                }
                OP_STORE => {
                    *byte = reg;
                    pc += 1;
                }
                OP_NOP => {
                    // 垃圾操作：消耗时钟周期，迷惑分析者
                    pc += 1;
                }
                OP_EXIT => {
                    break;
                }
                _ => {
                    // 非法指令，直接退出
                    break;
                }
            }
        }
    }
}

/// 解密 .pero 模型数据，并应用白盒逆转换
pub fn decrypt_pero_data_secure(data: &[u8]) -> Result<Vec<u8>> {
    // 1. 基础解密 (XChaCha20-Poly1305)
    let mut decrypted = decrypt_pero_v2(data)
        .map_err(|e| Error::new(Status::GenericFailure, format!("解密失败: {}", e)))?;

    // 2. 白盒逆转换 (White-Box SPN Inverse)
    // 即使攻击者拿到了上面的 decrypted 数据，它依然是被白盒混淆过的
    apply_wbc_inverse(&mut decrypted);

    Ok(decrypted)
}
