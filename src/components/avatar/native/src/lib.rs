use napi_derive::napi;

mod crypto;
mod parser;
mod security;

use napi::bindgen_prelude::*;

/// 解析加密的模型数据
#[napi]
pub fn load_pero_model(
    encrypted_data: Buffer,
    key: Buffer,
) -> napi::Result<parser::ParsedModelData> {
    // 0. 安全检查 (Security Check)
    // 如果检测到调试器，拒绝服务
    if security::is_debugged() {
        // 返回一个模糊的错误，不直接提示 "Debugger Detected"
        return Err(napi::Error::new(
            napi::Status::GenericFailure,
            obfstr::obfstr!("System Integrity Check Failed (Error 0x80004005)").to_string(),
        ));
    }

    // 1. Decrypt
    let decrypted = crypto::decrypt_pero_data(encrypted_data.as_ref(), key.as_ref())?;

    // 2. Parse & Generate Geometry
    parser::parse_model(&decrypted)
}

/// 获取当前的安全状态
/// 如果检测到调试器，返回 true
#[napi]
pub fn get_security_status() -> bool {
    security::is_debugged()
}

/// 这是一个示例函数，后续会被移除
#[napi]
pub fn sum(a: i32, b: i32) -> i32 {
    a + b
}
