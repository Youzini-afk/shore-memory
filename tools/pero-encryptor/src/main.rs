use anyhow::{Context, Result};
use chacha20poly1305::{
    aead::{Aead, AeadCore, KeyInit, OsRng},
    XChaCha20Poly1305,
};
use clap::{Parser, Subcommand};
use hkdf::Hkdf;
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use std::fs;
use std::path::PathBuf;

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
const PERO_VERSION: u16 = 2;
const HEADER_SIZE: usize = 10; // Magic(4) + Version(2) + MetaLen(4)
const SALT_SIZE: usize = 32;
const NONCE_SIZE: usize = 24;

#[derive(Debug, Serialize, Deserialize)]
struct PeroMetadata {
    pub original_type: String,
    pub created_at: String,
    pub original_size: u64,
}

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    Encrypt {
        #[arg(short, long)]
        input: PathBuf,
        #[arg(short, long)]
        output: PathBuf,
        #[arg(short, long)]
        key: Option<String>,
    },
    Decrypt {
        #[arg(short, long)]
        input: PathBuf,
        #[arg(short, long)]
        output: PathBuf,
        #[arg(short, long)]
        key: Option<String>,
    },
    Info {
        #[arg(short, long)]
        input: PathBuf,
    },
    GenKey,
}

fn main() -> Result<()> {
    let args = Args::parse();

    match args.command {
        Commands::Encrypt { input, output, key } => encrypt_file(&input, &output, key.as_deref())?,
        Commands::Decrypt { input, output, key } => decrypt_file(&input, &output, key.as_deref())?,
        Commands::Info { input } => show_info(&input)?,
        Commands::GenKey => generate_key()?,
    }

    Ok(())
}

fn generate_key() -> Result<()> {
    let mut key = [0u8; 32];
    OsRng.fill_bytes(&mut key);
    println!("生成的 32 字节主密钥 (hex):");
    println!("{}", hex::encode(key));
    println!("\n请妥善保管此密钥！");
    Ok(())
}

fn show_info(input: &PathBuf) -> Result<()> {
    let data = fs::read(input).context("无法读取输入文件")?;

    if data.len() < HEADER_SIZE {
        anyhow::bail!("文件太小，不是有效的 .pero 文件");
    }

    let magic = &data[0..4];
    if magic != PERO_MAGIC {
        anyhow::bail!("无效的 .pero 文件：魔数不匹配");
    }

    let version = u16::from_le_bytes([data[4], data[5]]);
    let meta_len = u32::from_le_bytes([data[6], data[7], data[8], data[9]]) as usize;

    if data.len() < HEADER_SIZE + meta_len {
        anyhow::bail!("文件损坏：元数据长度超出文件大小");
    }

    let meta_json = &data[HEADER_SIZE..HEADER_SIZE + meta_len];
    let metadata: PeroMetadata = serde_json::from_slice(meta_json).context("无法解析元数据")?;

    println!("📁 .pero 文件信息");
    println!("────────────────────────────────");
    println!("版本号: {}", version);
    println!("原始文件类型: {}", metadata.original_type);
    println!("创建时间: {}", metadata.created_at);
    println!("原始大小: {} bytes", metadata.original_size);

    let encrypted_size = data.len() - HEADER_SIZE - meta_len - SALT_SIZE - NONCE_SIZE;
    println!("加密数据大小: {} bytes", encrypted_size);

    Ok(())
}

fn derive_key(master_key: &[u8], salt: &[u8]) -> Result<[u8; 32]> {
    let hkdf = Hkdf::<Sha256>::new(Some(salt), master_key);
    let mut derived_key = [0u8; 32];
    hkdf.expand(b"PERO_MODEL_ENCRYPTION_KEY_V2", &mut derived_key)
        .map_err(|_| anyhow::anyhow!("HKDF 密钥派生失败"))?;
    Ok(derived_key)
}

fn encrypt_file(input: &PathBuf, output: &PathBuf, key: Option<&str>) -> Result<()> {
    println!("🔒 Pero Encryptor v0.3.0");
    println!("输入文件: {:?}", input);
    println!("输出文件: {:?}", output);

    let plaintext = fs::read(input).context("无法读取输入文件")?;

    let master_key = if let Some(k) = key {
        hex::decode(k).context("无效的 hex 密钥")?
    } else {
        println!("⚠️  使用默认测试密钥（不推荐用于生产环境）");
        b"\xdb\x05\x5e\x7f\x6c\xc0\xfd\xf9\x3a\x1a\x34\x20\x99\x5b\x1e\x41\xa2\x04\xe6\x0e\x81\xed\x7f\x5f\xb5\x8f\x88\x02\x3b\x13\xce\xa2".to_vec()
    };

    if master_key.len() != 32 {
        anyhow::bail!("主密钥必须是 32 字节 (64 个 hex 字符)");
    }

    // 1. 生成随机 Salt 和 Nonce
    let mut salt = [0u8; SALT_SIZE];
    let nonce = XChaCha20Poly1305::generate_nonce(&mut OsRng);
    OsRng.fill_bytes(&mut salt);

    // 2. 使用 HKDF 派生会话密钥
    let derived_key = derive_key(&master_key, &salt)?;

    // 3. 标准 XChaCha20-Poly1305 加密
    let cipher = XChaCha20Poly1305::new_from_slice(&derived_key)
        .map_err(|_| anyhow::anyhow!("无效的密钥长度"))?;

    let mut ciphertext = cipher
        .encrypt(&nonce, plaintext.as_ref())
        .map_err(|_| anyhow::anyhow!("加密失败"))?;

    // 4. 魔改变换 (与解密端保持同步)
    let magic_pattern = obfstr::obfbytes!(b"PERO_CORE_MAGIC_PATTERN_2026");
    for (i, byte) in ciphertext.iter_mut().take(magic_pattern.len()).enumerate() {
        *byte ^= magic_pattern[i];
    }

    // 5. 构建元数据
    let original_type = input
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("unknown")
        .to_string();

    let metadata = PeroMetadata {
        original_type,
        created_at: chrono::Local::now().to_rfc3339(),
        original_size: plaintext.len() as u64,
    };
    let meta_json = serde_json::to_vec(&metadata)?;

    // 6. 构建完整的 .pero 文件
    let mut final_data = Vec::with_capacity(
        HEADER_SIZE + meta_json.len() + SALT_SIZE + NONCE_SIZE + ciphertext.len(),
    );

    // 头部
    final_data.extend_from_slice(PERO_MAGIC);
    final_data.extend_from_slice(&PERO_VERSION.to_le_bytes());
    final_data.extend_from_slice(&(meta_json.len() as u32).to_le_bytes());

    // 元数据
    final_data.extend_from_slice(&meta_json);

    // Salt + Nonce + Ciphertext
    final_data.extend_from_slice(&salt);
    final_data.extend_from_slice(&nonce);
    final_data.extend_from_slice(&ciphertext);

    fs::write(output, final_data).context("无法写入输出文件")?;

    println!("✅ 加密成功！输出大小: {} bytes", output.metadata()?.len());

    Ok(())
}

fn decrypt_file(input: &PathBuf, output: &PathBuf, key: Option<&str>) -> Result<()> {
    println!("🔓 解密模式");
    println!("输入文件: {:?}", input);
    println!("输出文件: {:?}", output);

    let data = fs::read(input).context("无法读取输入文件")?;

    if data.len() < HEADER_SIZE + SALT_SIZE + NONCE_SIZE + 16 {
        anyhow::bail!("文件太小");
    }

    // 1. 解析头部
    let magic = &data[0..4];
    if magic != PERO_MAGIC {
        anyhow::bail!("无效的 .pero 文件：魔数不匹配");
    }

    let version = u16::from_le_bytes([data[4], data[5]]);
    let meta_len = u32::from_le_bytes([data[6], data[7], data[8], data[9]]) as usize;

    if version != PERO_VERSION {
        anyhow::bail!(
            "不支持的文件版本: {} (当前仅支持 v{})",
            version,
            PERO_VERSION
        );
    }

    let _meta_json = &data[HEADER_SIZE..HEADER_SIZE + meta_len];
    let crypto_start = HEADER_SIZE + meta_len;

    // 2. 提取 Salt, Nonce, Ciphertext
    let salt = &data[crypto_start..crypto_start + SALT_SIZE];
    let nonce_bytes = &data[crypto_start + SALT_SIZE..crypto_start + SALT_SIZE + NONCE_SIZE];
    let ciphertext = &data[crypto_start + SALT_SIZE + NONCE_SIZE..];

    let master_key = if let Some(k) = key {
        hex::decode(k).context("无效的 hex 密钥")?
    } else {
        println!("⚠️  使用默认测试密钥");
        b"12345678901234567890123456789012".to_vec()
    };

    if master_key.len() != 32 {
        anyhow::bail!("主密钥必须是 32 字节");
    }

    // 3. 使用 HKDF 派生会话密钥
    let derived_key = derive_key(&master_key, salt)?;

    // 4. 逆魔改变换
    let mut ciphertext = ciphertext.to_vec();
    let magic_pattern = obfstr::obfbytes!(b"PERO_CORE_MAGIC_PATTERN_2026");
    for (i, byte) in ciphertext.iter_mut().take(magic_pattern.len()).enumerate() {
        *byte ^= magic_pattern[i];
    }

    // 5. XChaCha20-Poly1305 解密
    use chacha20poly1305::XNonce;
    let nonce = XNonce::from_slice(nonce_bytes);

    let cipher = XChaCha20Poly1305::new_from_slice(&derived_key)
        .map_err(|_| anyhow::anyhow!("无效的密钥长度"))?;

    let plaintext = cipher
        .decrypt(nonce, ciphertext.as_ref())
        .map_err(|_| anyhow::anyhow!("解密失败：密钥错误或数据损坏"))?;

    fs::write(output, plaintext).context("无法写入输出文件")?;

    println!("✅ 解密成功！");

    Ok(())
}
