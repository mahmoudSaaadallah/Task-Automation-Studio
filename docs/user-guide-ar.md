# دليل الاستخدام السريع (بالعربي)

هذا الدليل يشرح استخدام التطبيق الحالي من سطر الأوامر.

## 1) تجهيز البيئة
```powershell
cd "d:\MSaadallah\Code\Tasks Automation"
.\env\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

## 2) تجهيز ملف البيانات
أنشئ ملف Excel يحتوي الأعمدة التالية بالضبط:
- `first_name`
- `last_name`
- `email`

مثال: `data/employees.xlsx`

## 3) تسجيل جلسة تعليم (Teach Session)
ابدأ جلسة:
```powershell
tas teach start --name "Employee Signup Session"
```

سجّل الأحداث يدويًا:
```powershell
tas teach event --session-id <SESSION_ID> --type open_url --set url=https://zoom.us/signup
tas teach event --session-id <SESSION_ID> --type fill --set selector=email_input --set value='{{record.email}}'
tas teach checkpoint --session-id <SESSION_ID> --name "signup-submitted"
```

إنهاء الجلسة:
```powershell
tas teach finish --session-id <SESSION_ID>
```

تصدير الجلسة:
```powershell
tas teach export --session-id <SESSION_ID> --output-file artifacts/session.json
```

## 4) تحويل جلسة التعليم إلى Workflow قابل للتشغيل
```powershell
tas teach compile --session-id <SESSION_ID> --workflow-id employee_signup_v1 --output-file artifacts/employee_signup_v1.workflow.json
```

## 5) تشغيل Workflow
تشغيل آمن بدون تنفيذ خارجي (`dry-run`):
```powershell
tas run --workflow-file artifacts/employee_signup_v1.workflow.json --input-file data/employees.xlsx --dry-run
```

التشغيل الحقيقي (`live-run`) يحتاج تنفيذ handlers فعلية للمتصفح وتكوين البريد:
```powershell
tas run --workflow-file artifacts/employee_signup_v1.workflow.json --input-file data/employees.xlsx --live-run --email-host imap.example.com --email-username user@example.com --email-password SECRET
```

## 6) مخرجات التشغيل
- نتائج Excel: داخل `artifacts/` أو المسار الذي تحدده بـ `--output-file`.
- تقرير JSON: داخل `artifacts/` أو المسار الذي تحدده بـ `--report-file`.
- قاعدة البيانات: `data/app.db`.

## 7) أوامر مساعدة
```powershell
tas --help
tas run --help
tas teach --help
```
