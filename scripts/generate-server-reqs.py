import os

# 获取项目根目录的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

req_path = os.path.join(project_root, 'backend', 'requirements.txt')
out_path = os.path.join(project_root, 'backend', 'requirements-server.txt')

if not os.path.exists(req_path):
    print(f"错误: 未找到 {req_path}。")
    exit(1)

lines = open(req_path, encoding='utf-8').readlines()
with open(out_path, 'w', encoding='utf-8') as f:
    skip = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            f.write(line)
            continue
            
        # 检查是否为新包定义（行首，非注释）
        if not line.startswith(' ') and not line.startswith('#'):
            # 检查是否为排除的包之一
            if stripped.startswith(('pywin32==', 'pyautogui==', 'mouseinfo==', 'pyscreeze==', 'pygetwindow==', 'pymsgbox==', 'pyrect==', 'pytweening==')):
                skip = True
            else:
                skip = False
        
        if not skip:
            f.write(line)

print(f"已生成 {out_path}")
