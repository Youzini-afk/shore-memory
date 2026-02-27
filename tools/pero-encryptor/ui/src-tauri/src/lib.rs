use anyhow::{Context, Result};
use chacha20poly1305::{
    aead::{Aead, AeadCore, KeyInit, OsRng},
    XChaCha20Poly1305,
};
use hkdf::Hkdf;
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use std::fs;
use std::path::PathBuf;
use std::time::Instant;

const PERO_MAGIC: &[u8; 4] = b"PERO";
const PERO_VERSION: u16 = 3;
const HEADER_SIZE: usize = 10;
const SALT_SIZE: usize = 32;
const NONCE_SIZE: usize = 24;

#[derive(Debug, Serialize, Deserialize)]
pub struct EncryptResult {
    pub success: bool,
    pub message: String,
    pub output_size: Option<u64>,
    #[serde(rename = "fileCount")]
    pub file_count: Option<usize>,
}

#[cfg(target_os = "windows")]
use windows::Win32::System::Diagnostics::Debug::{CheckRemoteDebuggerPresent, IsDebuggerPresent};
#[cfg(target_os = "windows")]
use windows::Win32::System::Threading::GetCurrentProcess;

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

#[inline(never)]
fn extract_entropy_fake(input: &[u8]) -> u32 {
    let mut hash = 0x811c9dc5u32;
    for &b in input {
        hash ^= b as u32;
        hash = hash.wrapping_mul(0x01000193);
    }
    hash = (hash ^ (hash >> 16)).wrapping_mul(0x85ebca6b);
    hash = (hash ^ (hash >> 13)).wrapping_mul(0xc2b2ae35);
    hash ^ (hash >> 16)
}

#[inline(never)]
fn verify_integrity_fake(data: &[u8]) -> bool {
    if data.len() < 4 {
        return false;
    }
    let check = extract_entropy_fake(&data[..data.len() / 2]);
    let expected = u32::from_le_bytes([data[0], data[1], data[2], data[3]]);
    std::hint::black_box(check == expected || true)
}

fn assemble_master_key() -> [u8; 32] {
    let mut key = [0u8; 32];
    let dummy_data = obfstr::obfbytes!(b"SYSTEM_ENTROPY_CHECK_V3");
    if extract_entropy_fake(dummy_data) == 0x12345678 {
        key.copy_from_slice(&assemble_decoy_key());
        return key;
    }
    let p1 = obfstr::obfbytes!(b"\xdb\x05\x5e\x7f\x6c\xc0\xfd\xf9");
    let p2 = obfstr::obfbytes!(b"\x3a\x1a\x34\x20\x99\x5b\x1e\x41");
    let p3 = obfstr::obfbytes!(b"\xa2\x04\xe6\x0e\x81\xed\x7f\x5f");
    let p4 = obfstr::obfbytes!(b"\xb5\x8f\x88\x02\x3b\x13\xce\xa2");
    let mask = obfstr::obfbytes!(b"PERO_DYNAMIC_XOR_MASK_2026");
    for i in 0..8 {
        key[i] = (p1[i] ^ mask[i % mask.len()]) ^ mask[i % mask.len()];
        key[i + 8] = (p2[i] ^ mask[(i + 8) % mask.len()]) ^ mask[(i + 8) % mask.len()];
        key[i + 16] = (p3[i] ^ mask[(i + 16) % mask.len()]) ^ mask[(i + 16) % mask.len()];
        key[i + 24] = (p4[i] ^ mask[(i + 24) % mask.len()]) ^ mask[(i + 24) % mask.len()];
    }
    if !verify_integrity_fake(&key) {
        key[0] ^= 0xFF;
    }
    key
}

fn derive_key(master_key_input: &[u8], salt: &[u8]) -> Result<[u8; 32]> {
    if is_debugger_detected() {
        return Ok(assemble_decoy_key());
    }
    if salt.len() == 32 && salt[0] == 0xCC {
        let mut decoy = assemble_decoy_key();
        decoy[0] = salt[1];
        return Ok(decoy);
    }
    let mut check_sum = 0u8;
    for &b in master_key_input {
        check_sum = check_sum.wrapping_add(b);
    }
    if check_sum == 0 {
        return Err(anyhow::anyhow!(
            obfstr::obfstr!("KEY_CHECKSUM_ERR").to_string()
        ));
    }
    let _decoy = assemble_decoy_key();
    let hkdf = Hkdf::<Sha256>::new(Some(salt), master_key_input);
    let mut derived_key = [0u8; 32];
    hkdf.expand(b"PERO_MODEL_ENCRYPTION_KEY", &mut derived_key)
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

const OP_LOAD: u8 = 0x1A;
const OP_SBOX1: u8 = 0x2B;
const OP_SBOX2: u8 = 0x3C;
const OP_XOR: u8 = 0x4D;
const OP_STORE: u8 = 0x5E;
const OP_EXIT: u8 = 0xFF;
const OP_NOP: u8 = 0x90;

fn apply_wbc_forward(data: &mut [u8]) {
    let bytecode: [u8; 12] = [
        OP_LOAD, OP_NOP, OP_SBOX1, OP_NOP, OP_XOR, OP_NOP, OP_NOP, OP_SBOX2, OP_STORE, OP_NOP,
        OP_EXIT, 0x00,
    ];
    for (i, byte) in data.iter_mut().enumerate() {
        let mut reg: u8 = 0;
        let mut pc: usize = 0;
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

#[derive(Debug, Serialize)]
struct ContainerMetadata {
    pub original_type: String,
    pub created_at: String,
    pub total_files: usize,
    pub file_list: Vec<String>,
}

fn pack_folder_to_tar(folder_path: &PathBuf) -> Result<(Vec<u8>, Vec<String>)> {
    let mut tar_buffer = Vec::new();
    let mut file_list = Vec::new();

    {
        let mut tar_builder = tar::Builder::new(&mut tar_buffer);

        fn add_dir_recursively(
            builder: &mut tar::Builder<&mut Vec<u8>>,
            dir: &PathBuf,
            base: &PathBuf,
            file_list: &mut Vec<String>,
        ) -> Result<()> {
            if !dir.exists() {
                return Err(anyhow::anyhow!("目录不存在: {}", dir.display()));
            }

            for entry in fs::read_dir(dir)? {
                let entry = entry?;
                let path = entry.path();
                let relative_path = path.strip_prefix(base)?;

                if path.is_dir() {
                    add_dir_recursively(builder, &path, base, file_list)?;
                } else {
                    let mut header = tar::Header::new_gnu();
                    let metadata = fs::metadata(&path)?;
                    header.set_size(metadata.len());
                    header.set_mode(0o644);
                    header.set_cksum();

                    builder.append_data(&mut header, relative_path, fs::File::open(&path)?)?;

                    if let Some(path_str) = relative_path.to_str() {
                        file_list.push(path_str.replace('\\', "/"));
                    }
                }
            }
            Ok(())
        }

        add_dir_recursively(&mut tar_builder, folder_path, folder_path, &mut file_list)?;
        tar_builder.finish()?;
    }

    Ok((tar_buffer, file_list))
}

fn do_encrypt_folder(input_folder: &str, output_path: &str) -> Result<(u64, usize)> {
    let input = PathBuf::from(input_folder);
    let output = PathBuf::from(output_path);

    if !input.is_dir() {
        return Err(anyhow::anyhow!("输入路径必须是文件夹"));
    }

    let (mut tar_data, file_list) = pack_folder_to_tar(&input)?;
    let file_count = file_list.len();

    if file_count == 0 {
        return Err(anyhow::anyhow!("文件夹为空，没有可加密的文件"));
    }

    apply_wbc_forward(&mut tar_data);

    let _decoy = assemble_decoy_key();
    let mut master_key = assemble_master_key().to_vec();

    let mut salt = [0u8; SALT_SIZE];
    let nonce = XChaCha20Poly1305::generate_nonce(&mut OsRng);
    OsRng.fill_bytes(&mut salt);

    let derived_key = derive_key(&master_key, &salt)?;

    for b in master_key.iter_mut() {
        *b = 0x00;
    }

    let cipher = XChaCha20Poly1305::new_from_slice(&derived_key)
        .map_err(|_| anyhow::anyhow!(obfstr::obfstr!("无效的密钥长度").to_string()))?;

    let mut ciphertext = cipher
        .encrypt(&nonce, tar_data.as_ref())
        .map_err(|_| anyhow::anyhow!(obfstr::obfstr!("加密失败").to_string()))?;

    let magic_pattern = obfstr::obfbytes!(b"PERO_CORE_MAGIC_PATTERN_2026");
    for (i, byte) in ciphertext.iter_mut().take(magic_pattern.len()).enumerate() {
        *byte ^= magic_pattern[i];
    }

    let container_meta = ContainerMetadata {
        original_type: "pero_container".to_string(),
        created_at: chrono::Local::now().to_rfc3339(),
        total_files: file_count,
        file_list,
    };
    let meta_json = serde_json::to_vec(&container_meta)?;

    let mut final_data = Vec::with_capacity(
        HEADER_SIZE + meta_json.len() + SALT_SIZE + NONCE_SIZE + ciphertext.len(),
    );

    final_data.extend_from_slice(PERO_MAGIC);
    final_data.extend_from_slice(&PERO_VERSION.to_le_bytes());
    final_data.extend_from_slice(&(meta_json.len() as u32).to_le_bytes());
    final_data.extend_from_slice(&meta_json);
    final_data.extend_from_slice(&salt);
    final_data.extend_from_slice(&nonce);
    final_data.extend_from_slice(&ciphertext);

    fs::write(&output, final_data).context("无法写入输出文件")?;

    Ok((output.metadata()?.len(), file_count))
}

#[tauri::command]
fn encrypt_folder(input_folder: String, output_path: String) -> EncryptResult {
    match do_encrypt_folder(&input_folder, &output_path) {
        Ok((size, count)) => EncryptResult {
            success: true,
            message: format!("加密成功！共打包 {} 个文件，输出大小: {} 字节", count, size),
            output_size: Some(size),
            file_count: Some(count),
        },
        Err(e) => EncryptResult {
            success: false,
            message: format!("加密失败: {}", e),
            output_size: None,
            file_count: None,
        },
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![encrypt_folder])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
