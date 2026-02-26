#!/usr/bin/env python3
"""Fix Nginx config - writes clean proxy_pass without any URL corruption"""
import subprocess, os

proxy_url = "http" + "://" + "127.0.0.1" + ":" + "8000"

config = f"""server {{
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location / {{
        proxy_pass {proxy_url};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }}
}}
"""

with open("/etc/nginx/sites-available/dashboard", "w") as f:
    f.write(config)

if os.path.exists("/etc/nginx/sites-enabled/default"):
    os.remove("/etc/nginx/sites-enabled/default")

os.system("ln -sf /etc/nginx/sites-available/dashboard /etc/nginx/sites-enabled/dashboard")

result = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
print(result.stderr)

if result.returncode == 0:
    os.system("systemctl restart nginx")
    print("Nginx restarted successfully!")
    with open("/etc/nginx/sites-available/dashboard") as f:
        for line in f:
            if "proxy_pass" in line:
                print(f"Config proxy_pass line: {line.strip()}")
                if "[" in line or "]" in line or "(" in line or ")" in line:
                    print("ERROR: URL is still corrupted!")
                else:
                    print("URL is CLEAN!")
else:
    print("Nginx config test FAILED!")
