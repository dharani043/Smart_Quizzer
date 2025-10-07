# 🔐 SECURITY CLEANUP GUIDE

## ⚠️ CRITICAL: Before GitHub Upload

### 1. Files Already Created (Safe for GitHub)
- ✅ `README.md` - Clean documentation
- ✅ `.env.example` - Template with placeholders
- ✅ `.gitignore` - Protects sensitive files
- ✅ `requirements.txt` - Clean dependencies
- ✅ `manage.py` - Standard Django file

### 2. Copy Your Project Files
**Copy these folders from `C:\Users\Dharanishankar\Desktop\INFOSYS\sample\` to this folder:**

```
Smart_Quizzer/
├── base/                    # Copy entire base folder
├── sample/                  # Copy entire sample folder
├── templates/ (if exists)   # Copy templates folder
└── static/ (if exists)      # Copy static folder
```

### 3. CRITICAL: Clean API Keys Before Upload

**In `base/llm_client.py` - Replace:**
```python
genai.configure(api_key="AIzaSyAr4zAzbPoB7UCzA9N8BwJCq5CQYMZQPFk")
```

**With:**
```python
import os
genai.configure(api_key=os.getenv('GOOGLE_AI_API_KEY'))
```

**In `base/views.py` - Replace all hardcoded API keys with:**
```python
import os
genai.configure(api_key=os.getenv('GOOGLE_AI_API_KEY'))
```

### 4. Clean settings.py
**In `sample/settings.py` - Replace:**
```python
SECRET_KEY = 'django-insecure-!7h3%oh3!(74abh$i5v!db@zle4c%qj(wr7hhrb7f+xd86t))4'
```

**With:**
```python
from decouple import config
SECRET_KEY = config('SECRET_KEY', default='your-secret-key-here')
```

**Replace database config:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

### 5. Files to NEVER Upload
- ❌ `.env` (your actual API keys)
- ❌ `db.sqlite3` (database with user data)
- ❌ `api key for gemini.txt`
- ❌ Any file with real passwords/keys

### 6. Upload Checklist
- [ ] Copied all project files to Smart_Quizzer folder
- [ ] Removed all hardcoded API keys
- [ ] Cleaned settings.py
- [ ] Verified .gitignore protects sensitive files
- [ ] No real API keys in any file
- [ ] Database files excluded

### 7. GitHub Upload Steps
1. **Initialize git in Smart_Quizzer folder**
2. **Add .gitignore first**: `git add .gitignore`
3. **Add all other files**: `git add .`
4. **Commit**: `git commit -m "Initial commit"`
5. **Push to GitHub**

---

**⚠️ DOUBLE-CHECK: Search entire folder for your API key before upload!**