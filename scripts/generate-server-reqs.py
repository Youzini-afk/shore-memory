import os

# Get absolute path to project root
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

req_path = os.path.join(project_root, 'backend', 'requirements.txt')
out_path = os.path.join(project_root, 'backend', 'requirements-server.txt')

if not os.path.exists(req_path):
    print(f"Error: {req_path} not found.")
    exit(1)

lines = open(req_path, encoding='utf-8').readlines()
with open(out_path, 'w', encoding='utf-8') as f:
    skip = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            f.write(line)
            continue
            
        # Check if it's a new package definition (start of line, not comment)
        if not line.startswith(' ') and not line.startswith('#'):
            # Check if it is one of the excluded packages
            if stripped.startswith(('pywin32==', 'pyautogui==', 'mouseinfo==', 'pyscreeze==', 'pygetwindow==', 'pymsgbox==', 'pyrect==', 'pytweening==')):
                skip = True
            else:
                skip = False
        
        if not skip:
            f.write(line)

print(f"Generated {out_path}")
