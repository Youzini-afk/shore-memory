
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const https = require('https');
const AdmZip = require('adm-zip');

// Configuration
const PYTHON_VERSION = '3.10.11';
const PYTHON_URL = `https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip`;
const PROJECT_ROOT = path.resolve(__dirname, '..');
const RESOURCES_DIR = path.join(PROJECT_ROOT, 'resources');
const PYTHON_DEST = path.join(RESOURCES_DIR, 'python');
const SITE_PACKAGES = path.join(PYTHON_DEST, 'Lib', 'site-packages');
const BACKEND_DIR = path.join(PROJECT_ROOT, 'backend');

// Colors for console output
const colors = {
    reset: '\x1b[0m',
    bright: '\x1b[1m',
    green: '\x1b[32m',
    yellow: '\x1b[33m',
    red: '\x1b[31m',
    cyan: '\x1b[36m'
};

function log(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const color = type === 'error' ? colors.red : type === 'success' ? colors.green : type === 'warning' ? colors.yellow : colors.cyan;
    console.log(`${colors.bright}[${timestamp}] ${color}${message}${colors.reset}`);
}

async function downloadFile(url, dest) {
    return new Promise((resolve, reject) => {
        const file = fs.createWriteStream(dest);
        https.get(url, (response) => {
            if (response.statusCode !== 200) {
                reject(new Error(`Failed to download: ${response.statusCode}`));
                return;
            }
            response.pipe(file);
            file.on('finish', () => {
                file.close();
                resolve();
            });
        }).on('error', (err) => {
            fs.unlink(dest, () => {});
            reject(err);
        });
    });
}

function ensureDir(dir) {
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
}

const GET_PIP_URL = 'https://bootstrap.pypa.io/get-pip.py';

async function setupPython() {
    log('Step 1: Setting up Embedded Python Environment...');
    
    ensureDir(PYTHON_DEST);
    const zipPath = path.join(RESOURCES_DIR, 'python.zip');
    const getPipPath = path.join(RESOURCES_DIR, 'get-pip.py');
    const pythonExe = path.join(PYTHON_DEST, 'python.exe');

    // Check if Python is already set up
    if (fs.existsSync(pythonExe)) {
        log('Python environment appears to be already set up.', 'warning');
    } else {
        log(`Downloading Python ${PYTHON_VERSION}...`);
        try {
            await downloadFile(PYTHON_URL, zipPath);
            log('Download complete. Extracting...');
            
            const zip = new AdmZip(zipPath);
            zip.extractAllTo(PYTHON_DEST, true);
            
            fs.unlinkSync(zipPath); // Cleanup
            log('Extraction complete.', 'success');
        } catch (e) {
            log(`Failed to setup Python: ${e.message}`, 'error');
            process.exit(1);
        }
    }

    // Configure .pth to enable site-packages
    const pthFile = path.join(PYTHON_DEST, `python${PYTHON_VERSION.split('.').slice(0, 2).join('')}._pth`);
    if (fs.existsSync(pthFile)) {
        let content = fs.readFileSync(pthFile, 'utf8');
        if (content.includes('#import site')) {
            content = content.replace('#import site', 'import site');
            fs.writeFileSync(pthFile, content);
            log('Updated .pth file to enable site-packages.', 'success');
        }
    }

    // Install pip if not present
    // We check for pip by trying to run it
    try {
        execSync(`"${pythonExe}" -m pip --version`, { stdio: 'ignore' });
        log('pip is already installed in embedded Python.', 'success');
    } catch (e) {
        log('pip not found in embedded Python. Installing via get-pip.py...');
        try {
            await downloadFile(GET_PIP_URL, getPipPath);
            execSync(`"${pythonExe}" "${getPipPath}" --no-warn-script-location`, { stdio: 'inherit' });
            fs.unlinkSync(getPipPath);
            log('pip installed successfully.', 'success');
        } catch (err) {
            log(`Failed to install pip: ${err.message}`, 'error');
            process.exit(1);
        }
    }
}

function installDependencies() {
    log('Step 2: Installing Python Dependencies...');
    
    ensureDir(SITE_PACKAGES);
    const pythonExe = path.join(PYTHON_DEST, 'python.exe');

    try {
        // Use the embedded python's pip!
        // Note: We don't need --target anymore if we use the embedded python's pip, 
        // as it will install to its own site-packages by default.
        
        // 1. Install Torch (CPU)
        log('Installing PyTorch (CPU)...');
        // Check if torch is already installed to save time
        try {
            execSync(`"${pythonExe}" -m pip show torch`, { stdio: 'ignore' });
            log('PyTorch already installed, skipping.', 'warning');
        } catch {
            execSync(`"${pythonExe}" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --no-warn-script-location`, { stdio: 'inherit' });
        }

        // 2. Install Requirements
        log('Installing requirements.txt...');
        const reqPath = path.join(BACKEND_DIR, 'requirements.txt');
        execSync(`"${pythonExe}" -m pip install -r "${reqPath}" --no-warn-script-location`, { stdio: 'inherit' });
        
        log('Dependencies installed successfully.', 'success');
    } catch (e) {
        log(`Failed to install dependencies: ${e.message}`, 'error');
        process.exit(1);
    }
}

function buildRustExtensions() {
    log('Step 3: Building/Installing Rust Core Extensions...');

    const pythonExe = path.join(PYTHON_DEST, 'python.exe');

    // Check for maturin in embedded python
    try {
        execSync(`"${pythonExe}" -m maturin --version`, { stdio: 'ignore' });
    } catch (e) {
        log('Maturin not found in embedded Python. Installing...', 'warning');
        execSync(`"${pythonExe}" -m pip install maturin`, { stdio: 'inherit' });
    }

    const extensions = [
        {
            name: 'pero_memory_core',
            path: path.join(BACKEND_DIR, 'rust_core', 'Cargo.toml'),
            dir: path.join(BACKEND_DIR, 'rust_core')
        },
        {
            name: 'pero_vision_core',
            path: path.join(BACKEND_DIR, 'vision_core', 'Cargo.toml'),
            dir: path.join(BACKEND_DIR, 'vision_core')
        },
        {
            name: 'nit_rust_runtime',
            path: path.join(BACKEND_DIR, 'nit_core', 'interpreter', 'rust_binding', 'Cargo.toml'),
            dir: path.join(BACKEND_DIR, 'nit_core', 'interpreter', 'rust_binding')
        }
    ];

    const distDir = path.join(PROJECT_ROOT, 'dist_wheels');
    ensureDir(distDir);

    for (const ext of extensions) {
        if (!fs.existsSync(ext.path)) {
            log(`Skipping ${ext.name} (Cargo.toml not found)`, 'warning');
            continue;
        }

        // Try to find existing wheel in target/wheels to reuse
        const targetWheelsDir = path.join(ext.dir, 'target', 'wheels');
        let reused = false;
        
        if (fs.existsSync(targetWheelsDir)) {
             const wheels = fs.readdirSync(targetWheelsDir).filter(f => f.endsWith('.whl'));
             if (wheels.length > 0) {
                 // Sort by time, newest first
                 wheels.sort((a, b) => {
                     return fs.statSync(path.join(targetWheelsDir, b)).mtime.getTime() - 
                            fs.statSync(path.join(targetWheelsDir, a)).mtime.getTime();
                 });
                 const latestWheel = path.join(targetWheelsDir, wheels[0]);
                 log(`Found existing wheel for ${ext.name}: ${wheels[0]}. Reusing...`, 'success');
                 
                 try {
                    execSync(`"${pythonExe}" -m pip install "${latestWheel}" --force-reinstall --no-deps`, { stdio: 'inherit' });
                    reused = true;
                 } catch (e) {
                     log(`Failed to install existing wheel: ${e.message}. Will attempt rebuild.`, 'warning');
                 }
             }
        }

        if (!reused) {
            log(`Building ${ext.name}...`);
            try {
                // Build wheel using embedded python's maturin
                // We use --interpreter to ensure it builds for our embedded python version
                execSync(`"${pythonExe}" -m maturin build --release --manifest-path "${ext.path}" --out "${distDir}" --interpreter "${pythonExe}"`, { stdio: 'inherit' });
                
                // Find the generated wheel
                const files = fs.readdirSync(distDir);
                const wheel = files.find(f => f.includes(ext.name.replace(/-/g, '_')) && f.endsWith('.whl')); // Rust crate names use underscores
                
                if (wheel) {
                    log(`Installing ${wheel}...`);
                    const wheelPath = path.join(distDir, wheel);
                    execSync(`"${pythonExe}" -m pip install "${wheelPath}" --force-reinstall --no-deps`, { stdio: 'inherit' });
                    // Cleanup wheel
                    fs.unlinkSync(wheelPath);
                } else {
                    log(`Failed to find wheel for ${ext.name}`, 'error');
                }
            } catch (e) {
                log(`Failed to build/install ${ext.name}: ${e.message}`, 'error');
            }
        }
    }
    
    // Cleanup dist dir
    if (fs.existsSync(distDir) && fs.readdirSync(distDir).length === 0) {
        fs.rmdirSync(distDir);
    }
}

function buildBinaryTools() {
    log('Step 4: Building Binary Tools...');

    // Helper to check and copy existing binary
    const checkAndCopy = (srcDirs, dest, name) => {
        for (const dir of srcDirs) {
            const possiblePath = path.join(dir, name);
            if (fs.existsSync(possiblePath)) {
                log(`Found existing binary for ${name} at ${possiblePath}. Reusing...`, 'success');
                fs.copyFileSync(possiblePath, dest);
                return true;
            }
        }
        return false;
    };

    // 1. CodeSearcher
    const codeSearcherSrc = path.join(BACKEND_DIR, 'nit_core/tools/work/CodeSearcher/src');
    const codeSearcherDest = path.join(BACKEND_DIR, 'nit_core/tools/work/CodeSearcher/CodeSearcher.exe');
    
    if (fs.existsSync(path.join(codeSearcherSrc, 'Cargo.toml'))) {
        // Check existing first
        const searchPaths = [
            path.join(codeSearcherSrc, 'target/release'),
            path.join(codeSearcherSrc, '../target/release'),
            path.join(PROJECT_ROOT, 'target/release')
        ];
        
        if (!checkAndCopy(searchPaths, codeSearcherDest, 'CodeSearcher.exe')) {
             log('Building CodeSearcher...');
             try {
                execSync(`cargo build --release --manifest-path "${path.join(codeSearcherSrc, 'Cargo.toml')}"`, { stdio: 'inherit' });
                // Try copy again after build
                if (!checkAndCopy(searchPaths, codeSearcherDest, 'CodeSearcher.exe')) {
                     log('Could not locate built CodeSearcher.exe even after build', 'error');
                }
             } catch (e) {
                log(`Failed to build CodeSearcher: ${e.message}`, 'error');
             }
        }
    }

    // 2. nit_terminal_auditor (Wasm)
    const auditorSrc = path.join(BACKEND_DIR, 'nit_core/nit_terminal_auditor');
    const auditorDest = path.join(BACKEND_DIR, 'nit_core/tools/work/TerminalExecutor/auditor.wasm');
    
    if (fs.existsSync(path.join(auditorSrc, 'Cargo.toml'))) {
         const searchPaths = [
            path.join(auditorSrc, 'target/wasm32-unknown-unknown/release'),
            path.join(PROJECT_ROOT, 'target/wasm32-unknown-unknown/release')
        ];

        if (!checkAndCopy(searchPaths, auditorDest, 'nit_terminal_auditor.wasm')) {
            log('Building nit_terminal_auditor (Wasm)...');
            try {
                try {
                    execSync('rustup target add wasm32-unknown-unknown', { stdio: 'ignore' });
                } catch (e) {}
    
                execSync(`cargo build --release --target wasm32-unknown-unknown --manifest-path "${path.join(auditorSrc, 'Cargo.toml')}"`, { stdio: 'inherit' });
                
                if (!checkAndCopy(searchPaths, auditorDest, 'nit_terminal_auditor.wasm')) {
                    log('Could not locate built nit_terminal_auditor.wasm', 'error');
                }
            } catch (e) {
                log(`Failed to build nit_terminal_auditor: ${e.message}`, 'error');
            }
        }
    }
}

async function main() {
    log('Starting Local Backend Build Process...', 'bright');
    
    await setupPython();
    installDependencies();
    buildRustExtensions();
    buildBinaryTools();
    
    log('Backend Build Process Completed!', 'success');
}

main().catch(err => {
    console.error(err);
    process.exit(1);
});
