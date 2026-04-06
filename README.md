# PythonAnywhere Auto-Renewal Bot

تجديد تلقائي لحسابات PythonAnywhere المتعددة كل 15 يوم عبر GitHub Actions.

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Automated-2088FF?logo=github-actions&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Multi-Account](https://img.shields.io/badge/Supports-Multi--Account-orange.svg)

---

## إعداد الـ Secrets

روح **Settings ← Secrets and variables ← Actions ← New repository secret**

### حساب واحد
| Secret | القيمة |
|--------|--------|
| `PA_USERNAME_1` | يوزرنيم الحساب |
| `PA_PASSWORD_1` | كلمة السر |
| `PA_LABEL_1` | اسم ودود (اختياري) مثل "My App" |

### حسابات متعددة — نفس النمط
```
PA_USERNAME_1  /  PA_PASSWORD_1  /  PA_LABEL_1
PA_USERNAME_2  /  PA_PASSWORD_2  /  PA_LABEL_2
PA_USERNAME_3  /  PA_PASSWORD_3  /  PA_LABEL_3
...
```
السكريبت بيكتشف الحسابات تلقائياً من 1 للأعلى — بس أضف الـ Secrets وخلاص.

---

## تفعيل صلاحيات الـ Workflow

**Settings ← Actions ← General ← Workflow permissions**
- اختر **Read and write permissions**
- فعّل **Allow GitHub Actions to create and approve pull requests**
- اضغط **Save**

---

## اختبار يدوي

**Actions ← Auto-Renew PythonAnywhere (Multi-Account) ← Run workflow**

---

## الجدول الزمني

الـ Workflow بيشتغل كل **1 و 15 من الشهر** الساعة **4:00 صباحاً UTC** (6:00 صباحاً بتوقيت مصر).

لتغيير الجدول عدّل السطر ده في `renew.yml`:
```yaml
- cron: '0 4 1,15 * *'
```

---

## اختبار محلي

```bash
pip install -r requirements.txt
cp .env.example .env
# عدّل .env بالبيانات الحقيقية
python renew_python_anywhere.py
```

---

## هيكل المشروع

```
python-Auto-Renewer/
├── .github/
│   ├── workflows/
│   │   └── renew.yml              # GitHub Actions workflow
│   └── logs/
│       └── workflow_runs.log      # سجل التشغيلات
├── renew_python_anywhere.py       # السكريبت الرئيسي
├── requirements.txt
├── .env.example                   # مثال للمتغيرات المحلية
├── .gitignore
└── README.md
```

---

## License — MIT
