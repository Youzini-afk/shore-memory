#[cfg(windows)]
use windows::Win32::System::Diagnostics::Debug::{CheckRemoteDebuggerPresent, IsDebuggerPresent};
#[cfg(windows)]
use windows::Win32::System::Threading::GetCurrentProcess;
#[cfg(windows)]
use windows::Win32::Foundation::BOOL;

/// 检测当前环境是否被调试
/// Detect if the current environment is being debugged
pub fn is_debugged() -> bool {
    #[cfg(windows)]
    unsafe {
        // 1. 基础 API 检测 (Basic API Check)
        // IsDebuggerPresent 是最基础的检测，检查 PEB 中的 BeingDebugged 标志
        if IsDebuggerPresent().as_bool() {
            return true;
        }

        // 2. 远程调试器检测 (Remote Debugger Check)
        // 检查是否被其他进程附加 (如 VS, OllyDbg 等)
        let mut present = BOOL(0);
        // 我们忽略返回值，只关心 present 的结果
        let _ = CheckRemoteDebuggerPresent(GetCurrentProcess(), &mut present);
        if present.as_bool() {
            return true;
        }

        // TODO: 添加更高级的检测 (如 RDTSC 计时检测, PEB 手动检查等)
        
        return false;
    }

    #[cfg(not(windows))]
    {
        // 非 Windows 环境暂时默认安全 (或者后续添加 ptrace 检测)
        false
    }
}
