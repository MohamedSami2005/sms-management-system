# Campus Communication Management System (CCMS)
> **A Unified Communication Platform for Educational Institutions**

[![Django 5](https://img.shields.io/badge/Django-5.1.7-green.svg)](https://www.djangoproject.com/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Bootstrap 5](https://img.shields.io/badge/Bootstrap-5.3-purple.svg)](https://getbootstrap.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

---

## 📌 Project Overview

**Campus Communication Management System (CCMS)** is an enterprise-grade, multi-departmental communication management platform designed specifically for educational institutions (Colleges, Universities, and Schools). 

Rather than acting as a standalone SMS gateway, CCMS serves as an **internal communication management layer** that integrates with existing HTTP SMS Gateway providers (such as Draft4SMS), telecom Telecom DLT registries, and institutional staff databases to deliver personalized, compliant, and audited transactional communications.

---

## 🌟 Key Features

### 1. Authentication & Role-Based Access Control (RBAC)
- Custom user model (`CustomUser`) with departmental mappings and staff employee IDs.
- Granular permissions for 6 system roles: **Administrator**, **Controller of Examinations (COE)**, **Admission**, **Accounts**, **Placement**, and **College Staff**.
- Persistent session security, login rate limiting, and password reset workflow.

### 2. Recipient & Department Management
- **Staff Directory**: Paginated data table supporting search across Name, Employee ID, Email, and Phone number, with filters by Department, Role, and Status.
- **Department Management**: Hierarchical college department management with soft-delete safeguards for active personnel.

### 3. DLT Template Management System
- Central repository for telecom DLT-approved SMS content templates.
- **Automatic Variable Extraction**: Regex engine automatically detects `{#var#}` and `{1}` placeholders.
- **Custom Variable Renaming**: Administrators can customize variable labels (e.g. `Student Name`, `Exam Date`, `Amount`) and default sample values.
- **Credit Estimator**: Real-time GSM 7-bit (160 chars) vs Unicode (70 chars) multipart credit calculation.
- **Bulk Excel/CSV Import & Export**: Import/export template definitions via `.xlsx` and `.csv`.

### 4. SMS Gateway Integration (Draft4SMS Compliance)
- **Zero Hardcoding**: Dynamically reads API URL, API Key, Sender ID (Header), DLT Entity ID, Route ID, HTTP Method, and Timeout settings from `SMSGatewayConfig`.
- **API Key Security**: Password-masked input field with Show/Hide toggle. Automatic log masking (`DRAF****7890`) prevents credential exposure in HTML, exceptions, or log files.
- **Resilience Engine**: 3 retries with exponential backoff (`1s`, `2s`, `4s`) on transient network errors or HTTP 5xx failures.
- **Live Diagnostics**: Web-based **Test Connection** latency testing (ms) and real-time **Check Balance** API.

### 5. Communication Engine
- **Single SMS Dispatch**: Real-time dynamic variable rendering, live phone preview sandbox, character counter, and SMS credit estimator.
- **Personalized Bulk Staff SMS Engine**: Maps template variables to staff database fields (`Staff Name`, `Employee ID`, `Department`, `Designation`, `Email`, `Mobile`, `Username`) or static values. Every recipient receives an individually generated message.
- **Live "Preview As" Sandbox**: Interactive recipient dropdown allowing real-time preview of personalized messages per staff member before batch execution.

### 6. Communication Logs & Analytics
- Immutable `SMSLog` audit trail recording sender, recipient, message body, status, credit cost, gateway transaction ID, and timestamp.
- DLR Delivery Report synchronization service automatically updating logs to `DELIVRD`, `REJECTD`, or `UNDELIV`.

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Framework** | Django 5.1 (Python 3.12) |
| **Database** | MySQL / SQLite3 (`pymysql` driver fallback) |
| **Frontend** | HTML5, Vanilla JavaScript, Bootstrap 5.3, Bootstrap Icons |
| **Form Management** | Django Crispy Forms (`crispy-bootstrap5`) |
| **Static Processing** | WhiteNoise Middleware |
| **Data Processing** | Pandas, OpenPyXL, Requests |

---

## 🏛️ System Architecture

```
Campus Communication Management System (CCMS)
├── Core Modules
│   ├── Authentication & Authorization (RBAC, CustomUser, Role)
│   ├── Recipient Management (Staff Directory, Departments)
│   ├── Communication Engine (Single SMS, Personalized Bulk SMS Engine, SMS Queue)
│   ├── DLT Template Management (Placeholder Extractor, Variable Mapper)
│   ├── Gateway Management (Draft4SMS Driver, Retry Engine, Credentials Config)
│   ├── Reports & Analytics (Audit Logs, Usage Metrics)
│   └── Administration (System Settings, Connectivity Diagnostics)
```

---

## 🚀 Installation & Setup Instructions

### Prerequisites
- Python 3.12+
- MySQL Server 8.0+ (or SQLite3 for development)

### 1. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/institution/ccms.git
cd sms-management-system

python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and set your credentials:
```env
SECRET_KEY=your-secure-django-secret-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost,testserver
USE_MYSQL=False
```

### 4. Apply Database Migrations
```bash
python manage.py migrate
```

### 5. Create Administrator Account
```bash
python manage.py createsuperuser
```

### 6. Run Automated Tests
```bash
python manage.py test apps.sms
```

### 7. Start Development Server
```bash
python manage.py runserver
```
Navigate to `http://127.0.0.1:8000/` in your browser.

---

## 🔮 Future Roadmap

- [ ] **Student Management**: Student directory with roll numbers, batches, and course mappings.
- [ ] **Parent Management**: Guardian phone & email association for automated student notifications.
- [ ] **Alumni Management**: Graduate network communication channels.
- [ ] **Contact Groups**: Custom dynamic broadcast groups.
- [ ] **Scheduled Messages**: Scheduled future dispatches with CRON runner.
- [ ] **Multi-Channel Integration**: Email, WhatsApp Business API, and Mobile Push Notifications.
- [ ] **REST APIs**: Secure REST API endpoints for external institutional systems.
- [ ] **Mobile Application**: Native iOS & Android staff communication portal.
- [ ] **Approval Workflows**: Multi-tier approval process for high-volume SMS dispatches.
- [ ] **Academic System Integrations**: Examination result alerts, Attendance shortage notices, and Fee payment reminders.

---

## 📄 License & Ownership
Copyright © 2026 Campus Communication Management System (CCMS). All rights reserved.
