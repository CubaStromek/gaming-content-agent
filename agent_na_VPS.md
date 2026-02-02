# Gaming Content Agent — nasazení na VPS

## Proč VPS

- Plná kontrola nad serverem (SSH, cron, systemd, libovolný software)
- Stálá cena ~€4/měsíc (Hetzner CX22: 2 vCPU, 4 GB RAM, 40 GB SSD)
- Žádné limity na dobu běhu pipeline (na rozdíl od serverless)
- Data na disku — JSON soubory, logy, output složky bez externího storage
- Možnost hostovat víc projektů na jednom serveru

---

## 1. Výběr a objednání serveru

### Hetzner Cloud (doporučeno)

| Parametr | Hodnota |
|----------|---------|
| Plán | CX22 (nebo CX11 pokud chceš šetřit) |
| OS | Ubuntu 24.04 LTS |
| Lokace | Falkenstein nebo Nuremberg (nejlevnější) |
| SSH klíč | Nahrát při vytváření (neklikej na heslo) |
| Firewall | Povolit porty 22 (SSH), 80 (HTTP), 443 (HTTPS) |

Alternativy: Contabo VPS S (~€5/měsíc), DigitalOcean Droplet ($6/měsíc).

---

## 2. Prvotní setup serveru

```bash
# Připojení
ssh root@<IP_SERVERU>

# Aktualizace systému
apt update && apt upgrade -y

# Vytvoření uživatele (neběžet vše jako root)
adduser gamebot
usermod -aG sudo gamebot

# Přepnutí na uživatele
su - gamebot
```

### Instalace závislostí

```bash
sudo apt install -y python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx
```

---

## 3. Nasazení aplikace

```bash
# Klonování repozitáře
cd /home/gamebot
git clone https://github.com/<TVUJ_REPO>/gaming-content-agent.git
cd gaming-content-agent

# Virtuální prostředí
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Konfigurace (.env)

```bash
cp .env.example .env
nano .env
```

Vyplnit:

```
CLAUDE_API_KEY=sk-ant-api03-...
EMAIL_TO=tvuj@email.cz
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tvuj@gmail.com
SMTP_PASSWORD=app-password
WP_URL=https://tvuj-wordpress.cz
WP_USER=api-user
WP_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
MAX_ARTICLES_PER_SOURCE=10
MIN_VIRALITY_SCORE=50
```

### Ověření, že pipeline funguje

```bash
source venv/bin/activate
python main.py
```

---

## 4. Automatizace — cron

```bash
crontab -e
```

### Varianta A: Spouštění pipeline každou hodinu (8:00–22:00)

```cron
0 8-22 * * * cd /home/gamebot/gaming-content-agent && /home/gamebot/gaming-content-agent/venv/bin/python auto_agent.py >> /home/gamebot/logs/auto_agent.log 2>&1
```

### Varianta B: Spouštění každé 3 hodiny (šetří API náklady)

```cron
0 */3 * * * cd /home/gamebot/gaming-content-agent && /home/gamebot/gaming-content-agent/venv/bin/python auto_agent.py >> /home/gamebot/logs/auto_agent.log 2>&1
```

### Příprava log adresáře

```bash
mkdir -p /home/gamebot/logs
```

> Poznámka: `auto_agent.py` zatím neexistuje — je to budoucí skript, který spojí
> pipeline (scrape → analyze → write → publish) do jednoho automatického běhu.
> Prozatím lze nahradit `main.py` pro samotnou analýzu bez auto-publishingu.

---

## 5. Flask dashboard — systemd služba

Vytvoření souboru `/etc/systemd/system/gamebot-web.service`:

```ini
[Unit]
Description=Gaming Content Agent - Web Dashboard
After=network.target

[Service]
User=gamebot
Group=gamebot
WorkingDirectory=/home/gamebot/gaming-content-agent
Environment="PATH=/home/gamebot/gaming-content-agent/venv/bin:/usr/bin"
ExecStart=/home/gamebot/gaming-content-agent/venv/bin/python web_app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable gamebot-web
sudo systemctl start gamebot-web

# Ověření
sudo systemctl status gamebot-web
```

Dashboard poběží na `localhost:5000`. Zpřístupníme ho přes nginx.

---

## 6. Nginx reverse proxy + HTTPS

### Nginx konfigurace

Soubor `/etc/nginx/sites-available/gamebot`:

```nginx
server {
    listen 80;
    server_name agent.tvoje-domena.cz;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/gamebot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### HTTPS (Let's Encrypt)

```bash
sudo certbot --nginx -d agent.tvoje-domena.cz
```

Certbot automaticky obnoví certifikáty (timer je součástí instalace).

---

## 7. Autentizace dashboardu

Na localhostu nebyla potřeba, na veřejném webu je nutná. Nejjednodušší varianty:

### Varianta A: HTTP Basic Auth přes nginx

```bash
sudo apt install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd gamebot
```

Přidat do nginx location bloku:

```nginx
location / {
    auth_basic "Gaming Agent";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://127.0.0.1:5000;
    # ... ostatní headers
}
```

### Varianta B: Login přímo ve Flask

Přidat Flask-Login nebo jednoduché session-based přihlášení do `web_app.py`.
Varianta A je rychlejší a nevyžaduje změny kódu.

---

## 8. Aktualizace kódu

```bash
cd /home/gamebot/gaming-content-agent
git pull origin master
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart gamebot-web
```

Případně si na to udělat jednoduchý deploy skript `/home/gamebot/deploy.sh`:

```bash
#!/bin/bash
cd /home/gamebot/gaming-content-agent
git pull origin master
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart gamebot-web
echo "Deploy hotovo."
```

---

## 9. Monitoring a údržba

### Logování

```bash
# Logy z automatického agenta
tail -f /home/gamebot/logs/auto_agent.log

# Logy z Flask dashboardu
sudo journalctl -u gamebot-web -f

# Logy z cronu
grep CRON /var/log/syslog
```

### Disk

`output/` složky se budou hromadit. Přidat cron na mazání starých běhů:

```cron
# Mazat output složky starší než 30 dní, každou neděli v 3:00
0 3 * * 0 find /home/gamebot/gaming-content-agent/output -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
```

### Alerting

Pokud `auto_agent.py` selže 3× za sebou, poslat email. Řešitelné uvnitř skriptu
přes existující `email_sender.py` nebo jednoduše kontrolou exit kódu v cron wrapperu.

---

## 10. Odhad nákladů

### Claude API — reálná spotřeba

Model: `claude-sonnet-4-20250514` (Sonnet 4)
Ceny: $3/MTok input, $15/MTok output

Reálně naměřeno: ~5 800 tokenů za běh analýzy → **~$0.02–0.06 za běh**.

| Scénář | Běhů/den | API cena/den | API cena/měsíc |
|--------|----------|-------------|----------------|
| Každou hodinu (8–22h) | 15 | ~$0.50 | ~$15 |
| Každé 3 hodiny | 8 | ~$0.25 | ~$8 |
| 1× denně | 1 | ~$0.04 | ~$1.20 |

> Pokud se k analýze přidá i generování článku (article_writer), spotřeba vzroste
> — prompt obsahuje scrapnuté zdrojové texty. Odhadem +5 000–15 000 tokenů na článek,
> tedy ~$0.05–0.20 navíc za vygenerovaný článek.

### Celkové měsíční náklady

| Položka | Cena/měsíc |
|---------|------------|
| Hetzner CX22 | €4.35 (~120 Kč) |
| Doména (.cz) | ~10 Kč (roční/12) |
| Claude API (15 běhů/den + 3 články/den) | ~$20 (~500 Kč) |
| Claude API (8 běhů/den + 1 článek/den) | ~$10 (~250 Kč) |
| **Celkem (střední varianta)** | **~400 Kč/měsíc** |

> Poznámka: Komentáře v kódu (`claude_analyzer.py:88`, `article_writer.py:267`)
> uvádějí "Haiku 4.5 pricing" ale skutečný model je Sonnet 4. Výpočet ceny v kódu
> je tedy podhodnocený — zobrazuje nižší částku než reálnou. Stojí za opravu.

---

## Shrnutí kroků

1. Objednat VPS na Hetzneru (CX22, Ubuntu 24.04)
2. Setup uživatele, Python, nginx
3. Naklonovat repo, vytvořit venv, vyplnit .env
4. Ověřit `python main.py`
5. Nastavit systemd službu pro Flask dashboard
6. Nginx reverse proxy + certbot HTTPS
7. Přidat HTTP Basic Auth
8. Nastavit cron pro automatické běhy
9. Nastavit cron pro čištění starých output složek
10. Napsat `auto_agent.py` pro plně autonomní pipeline
