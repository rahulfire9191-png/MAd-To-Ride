# 🏍️ Mad To Ride (MTR) — Flask Website

Riding community website for **Mad To Ride** founded by **Rahul "Madmax" Choudhari**.

---

## 📁 Project Structure

```
MTR Project 3.0/
├── MTR.py                  # Flask backend
├── requirements.txt        # Python dependencies
├── registrations.json      # Auto-created when first rider registers
├── uploads/               # User uploaded files (photos, documents)
├── sounds/                # Audio files
├── static/                # Static assets
└── templates/
    └── index.html         # Main website
```

---

## 🚀 How to Run

### Step 1 — Install Python
Make sure Python 3 is installed:
```bash
python --version
```

### Step 2 — Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3 — Run the App
```bash
python MTR.py
```

### Step 4 — Open in Browser
```
http://localhost:5000/
```

---

## 📋 Features

| Feature | Description |
|---------|-------------|
| **Rider Registration** | Complete registration form with file uploads |
| **Admin Panel** | Login protected admin dashboard |
| **Role Management** | Founder, Co-Founders, Captains, Members |
| **File Uploads** | Photos, driving licenses, bike images |
| **WhatsApp Integration** | Auto-redirect to WhatsApp group |
| **Mobile Responsive** | Works on all devices |

---

## 💾 How It Works

1. **Registration**: Riders fill comprehensive form with ID verification
2. **File Uploads**: Photos and documents uploaded to `/uploads/`
3. **Admin Management**: Protected admin panel for member management
4. **Role System**: Hierarchical roles with special permissions
5. **WhatsApp Integration**: Automatic group link after registration

---

## 🔐 Admin Access

- **Username**: `Madmax`
- **Password**: `Pa$$w0rd@Madmax`

---

## 🌐 Deploy Online (Free)

### Option A — Render.com (Recommended)
1. Push this folder to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your GitHub repo
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `gunicorn MTR:app`
6. Deploy!

### Option B — Railway.app
1. Push to GitHub
2. Go to [railway.app](https://railway.app) → New Project
3. Deploy from GitHub repo

### Option C — Vercel
1. Push to GitHub
2. Connect to Vercel
3. Configure as Python app

---

## 🔧 Configuration

### WhatsApp Group Link
Set in `MTR.py`:
```python
whatsapp_link = "https://chat.whatsapp.com/HbRgZJa1Rqm5Kbso36WDWf?mode=hqctcla"
```

### Admin Credentials
Change in `MTR.py`:
```python
ADMIN_USERNAME = 'Madmax'
ADMIN_PASSWORD = 'Pa$$w0rd@Madmax'
```

---

## 📊 Data Storage

- **Registrations**: Stored in `registrations.json`
- **Uploads**: Stored in `uploads/` directory
- **Logs**: Application logs in `app.log`

---

*Mad To Ride — Where the road calls and real riders answer. 🔥*
