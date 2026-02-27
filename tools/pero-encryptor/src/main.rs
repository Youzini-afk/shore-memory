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

use std::time::Instant;
#[cfg(target_os = "windows")]
use windows::Win32::System::Diagnostics::Debug::{CheckRemoteDebuggerPresent, IsDebuggerPresent};
#[cfg(target_os = "windows")]
use windows::Win32::System::Threading::GetCurrentProcess;

/// 多重反调试检查 (同步自解密端)
fn is_debugger_detected() -> bool {
    #[cfg(target_os = "windows")]
    unsafe {
        if IsDebuggerPresent().as_bool() {
            return true;
        }

        let mut is_remote_present = false.into();
        let _ = CheckRemoteDebuggerPresent(GetCurrentProcess(), &mut is_remote_present);
        if is_remote_present.as_bool() {
            return true;
        }

        let start = Instant::now();
        let mut sink = 0u64;
        for i in 0..100 {
            sink = sink.wrapping_add(i);
        }
        std::hint::black_box(sink);
        if start.elapsed().as_micros() > 500 {
            return true;
        }
    }
    false
}

/// 虚假密钥组装：用于迷惑分析
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

/// 密钥碎片化：不再以连续字节数组存储 Master Key
fn assemble_master_key() -> [u8; 32] {
    let mut key = [0u8; 32];

    // 碎片 1 (混淆后的)
    let p1 = obfstr::obfbytes!(b"\xdb\x05\x5e\x7f\x6c\xc0\xfd\xf9");
    let p2 = obfstr::obfbytes!(b"\x3a\x1a\x34\x20\x99\x5b\x1e\x41");
    let p3 = obfstr::obfbytes!(b"\xa2\x04\xe6\x0e\x81\xed\x7f\x5f");
    let p4 = obfstr::obfbytes!(b"\xb5\x8f\x88\x02\x3b\x13\xce\xa2");

    // 动态掩码
    let mask = obfstr::obfbytes!(b"PERO_DYNAMIC_XOR_MASK_2026");

    // 动态组装过程
    for i in 0..8 {
        key[i] = (p1[i] ^ mask[i % mask.len()]) ^ mask[i % mask.len()];
        key[i + 8] = (p2[i] ^ mask[(i + 8) % mask.len()]) ^ mask[(i + 8) % mask.len()];
        key[i + 16] = (p3[i] ^ mask[(i + 16) % mask.len()]) ^ mask[(i + 16) % mask.len()];
        key[i + 24] = (p4[i] ^ mask[(i + 24) % mask.len()]) ^ mask[(i + 24) % mask.len()];
    }

    key
}

/// 使用 HKDF-SHA256 派生会话密钥
fn derive_key(master_key_input: &[u8], salt: &[u8]) -> Result<[u8; 32]> {
    // 1. 动态检测调试环境
    if is_debugger_detected() {
        // 如果检测到调试器，加密端返回虚假密钥，生成的 .pero 文件将无法被正常解密
        // 这增加了攻击者拿到“正确加密文件”的难度喵！
        return Ok(assemble_decoy_key());
    }

    let hkdf = Hkdf::<Sha256>::new(Some(salt), master_key_input);
    let mut derived_key = [0u8; 32];
    hkdf.expand(b"PERO_MODEL_ENCRYPTION_KEY_V2", &mut derived_key)
        .map_err(|_| anyhow::anyhow!(obfstr::obfstr!("HKDF 密钥派生失败").to_string()))?;
    Ok(derived_key)
}

const SBOX1: [u8; 256] = [
    144, 65, 225, 117, 220, 85, 109, 21, 241, 29, 93, 245, 3, 250, 206, 159, 63, 189, 243, 205,
    249, 119, 60, 44, 123, 131, 11, 151, 101, 108, 135, 51, 227, 6, 45, 156, 77, 139, 121, 218, 15,
    163, 186, 125, 53, 148, 30, 138, 47, 236, 23, 87, 169, 9, 255, 28, 14, 196, 190, 184, 201, 172,
    191, 213, 212, 137, 147, 24, 140, 110, 229, 104, 251, 16, 219, 32, 84, 69, 10, 142, 204, 182,
    193, 66, 202, 37, 122, 97, 222, 41, 73, 217, 92, 153, 96, 145, 126, 49, 158, 155, 107, 195,
    124, 127, 157, 247, 46, 39, 55, 120, 208, 134, 173, 59, 181, 103, 174, 223, 78, 211, 232, 26,
    57, 180, 226, 207, 2, 154, 152, 118, 91, 20, 209, 252, 214, 17, 82, 199, 115, 86, 171, 18, 25,
    94, 62, 88, 136, 54, 235, 233, 1, 129, 194, 240, 128, 185, 188, 80, 12, 89, 38, 13, 4, 160,
    238, 228, 42, 246, 36, 111, 224, 237, 113, 33, 31, 200, 22, 75, 71, 95, 167, 168, 187, 72, 27,
    178, 162, 5, 35, 114, 0, 215, 183, 165, 52, 130, 100, 239, 234, 231, 98, 146, 76, 58, 74, 68,
    34, 64, 116, 166, 106, 164, 141, 253, 221, 90, 143, 40, 197, 210, 179, 61, 102, 248, 216, 170,
    7, 43, 133, 83, 230, 112, 198, 67, 203, 177, 132, 176, 19, 149, 254, 8, 105, 48, 81, 244, 56,
    70, 99, 50, 192, 242, 79, 161, 175, 150,
];
const SBOX2: [u8; 256] = [
    249, 10, 155, 93, 186, 124, 121, 173, 4, 251, 175, 210, 253, 36, 62, 85, 213, 176, 239, 70,
    110, 237, 118, 153, 171, 51, 221, 134, 48, 146, 108, 231, 56, 235, 101, 114, 89, 143, 100, 162,
    41, 19, 98, 104, 32, 5, 240, 166, 69, 169, 196, 80, 42, 28, 150, 60, 61, 78, 183, 181, 242,
    127, 68, 8, 238, 204, 200, 55, 220, 23, 133, 199, 111, 182, 201, 47, 125, 3, 123, 178, 247, 75,
    72, 154, 135, 224, 14, 45, 230, 208, 16, 119, 88, 161, 50, 142, 21, 13, 187, 191, 179, 211,
    128, 219, 79, 152, 202, 84, 130, 97, 147, 11, 245, 18, 0, 132, 39, 81, 29, 103, 188, 120, 248,
    17, 129, 226, 172, 131, 66, 222, 117, 105, 20, 167, 26, 7, 107, 139, 252, 236, 73, 214, 145, 2,
    223, 193, 195, 156, 38, 194, 206, 33, 225, 160, 228, 163, 34, 215, 250, 185, 207, 112, 99, 209,
    31, 244, 94, 15, 40, 164, 86, 227, 71, 67, 90, 218, 243, 1, 180, 255, 116, 149, 63, 232, 92,
    49, 57, 168, 159, 184, 102, 30, 233, 91, 25, 87, 106, 65, 46, 234, 144, 27, 217, 190, 59, 24,
    177, 198, 54, 203, 197, 9, 241, 216, 205, 140, 157, 22, 148, 192, 189, 122, 137, 109, 43, 174,
    58, 115, 96, 126, 52, 37, 151, 83, 229, 212, 165, 95, 44, 35, 138, 76, 170, 64, 254, 113, 158,
    136, 77, 74, 141, 12, 82, 53, 246, 6,
];
/// 轮密钥碎片化获取函数
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
/// 必须与解密端的指令集数值一致，或者至少在加密端保持逻辑对应
const OP_LOAD: u8 = 0x1A; // 加载字节
const OP_SBOX1: u8 = 0x2B; // 前位置换1
const OP_SBOX2: u8 = 0x3C; // 后位置换2
const OP_XOR: u8 = 0x4D; // 轮密钥异或
const OP_STORE: u8 = 0x5E; // 存储字节
const OP_EXIT: u8 = 0xFF; // 退出
const OP_NOP: u8 = 0x90; // 空指令 (垃圾指令)

/// 应用白盒前向转换 (通过自定义微型虚拟机执行)
fn apply_wbc_forward(data: &mut [u8]) {
    // 预定义的字节码序列：Load -> Sbox1 -> Xor -> Sbox2 -> Store
    // 为了增加难度，我们在其中穿插了大量的 NOP 垃圾指令
    let bytecode: [u8; 12] = [
        OP_LOAD, OP_NOP, OP_SBOX1, OP_NOP, OP_XOR, OP_NOP, OP_NOP, OP_SBOX2, OP_STORE, OP_NOP,
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
                    reg = SBOX1[reg as usize];
                    pc += 1;
                }
                OP_SBOX2 => {
                    reg = SBOX2[reg as usize];
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
                    pc += 1;
                }
                OP_EXIT => {
                    break;
                }
                _ => {
                    break;
                }
            }
        }
    }
}

fn encrypt_file(input: &PathBuf, output: &PathBuf, key: Option<&str>) -> Result<()> {
    println!("🔒 Pero Encryptor v0.3.0");
    println!("输入文件: {:?}", input);
    println!("输出文件: {:?}", output);

    let mut plaintext = fs::read(input).context("无法读取输入文件")?;

    // --- 步骤 1: 应用白盒混淆 (在标准加密之前) ---
    apply_wbc_forward(&mut plaintext);

    // 迷惑路径：调用虚假组装，但不使用其结果
    let _decoy = assemble_decoy_key();

    let mut master_key = if let Some(k) = key {
        hex::decode(k).context(obfstr::obfstr!("无效的 hex 密钥").to_string())?
    } else {
        // 使用碎片化拼凑的默认主密钥
        assemble_master_key().to_vec()
    };

    if master_key.len() != 32 {
        anyhow::bail!(obfstr::obfstr!("主密钥必须是 32 字节 (64 个 hex 字符)").to_string());
    }

    // 1. 生成随机 Salt 和 Nonce
    let mut salt = [0u8; SALT_SIZE];
    let nonce = XChaCha20Poly1305::generate_nonce(&mut OsRng);
    OsRng.fill_bytes(&mut salt);

    // 2. 使用 HKDF 派生会话密钥
    let derived_key = derive_key(&master_key, &salt)?;

    // 关键点：使用完主密钥后，立即从内存中擦除
    for b in master_key.iter_mut() {
        *b = 0x00;
    }

    // 3. 标准 XChaCha20-Poly1305 加密
    let cipher = XChaCha20Poly1305::new_from_slice(&derived_key)
        .map_err(|_| anyhow::anyhow!(obfstr::obfstr!("无效的密钥长度").to_string()))?;

    let mut ciphertext = cipher
        .encrypt(&nonce, plaintext.as_ref())
        .map_err(|_| anyhow::anyhow!(obfstr::obfstr!("加密失败").to_string()))?;

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
