use napi_derive::napi;

mod crypto;
mod parser;
mod security;

use napi::bindgen_prelude::*;

/// 解析加密的模型数据 ( .pero 格式 )
/// 不再接收外部密钥，安全性下放到 Rust 内部
#[napi]
pub fn load_pero_model(
    encrypted_data: Buffer,
    filter_patterns: Option<Vec<String>>,
) -> napi::Result<parser::ParsedModelData> {
    // 0. 安全检查 (Security Check)
    if security::is_debugged() {
        return Err(napi::Error::new(
            napi::Status::GenericFailure,
            obfstr::obfstr!("系统完整性检查失败 (Error 0x80004005)").to_string(),
        ));
    }

    // 1. 解密 (使用内部密钥)
    let decrypted = crypto::decrypt_pero_data_secure(encrypted_data.as_ref())?;

    // 2. 解析几何体
    let parsed_data = parser::parse_model_internal(&decrypted, filter_patterns)?;

    // 3. 直接返回解析后的对象，不再进行二进制打包
    // 数据安全性由 Rust 内部处理，TS 侧只负责渲染
    Ok(parsed_data)
}

/// 解析标准模型数据 ( .json 格式 )
/// 直接返回解析后的对象
#[napi]
pub fn load_standard_model(
    json_data: Buffer,
    filter_patterns: Option<Vec<String>>,
) -> napi::Result<parser::ParsedModelData> {
    let parsed_data = parser::parse_model_internal(json_data.as_ref(), filter_patterns)?;
    Ok(parsed_data)
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
