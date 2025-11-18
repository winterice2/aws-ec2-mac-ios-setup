# AWS EC2 Mac для iOS разработки: Пошаговая инструкция

## Быстрый расчет AWS кредитов

- **Стоимость EC2 Mac:** $1.083/час (mac1.metal)
- **Минимальная аренда:** 24 часа подряд (лицензия Apple) → минимум $26
- **AWS Free Tier кредиты:** $100 при регистрации + $100 за задания (6 мес)
- **Лимит использования:** $200 / $1.083 ≈ 184 ч (или ~7.7 дней)
- **Стратегия:** запускать только на время работы — хватит на 2 месяца по 4 ч/день

---

## Настройка: шаг за шагом

### 1. Аккаунт AWS и кредиты
- Зарегистрироваться: [aws.amazon.com/free](https://aws.amazon.com/free)
- Привязать карту — деньги не списываются, если не превысить $200
- Получить $100 сразу, еще $100 — за выполнение задач (запуск EC2, алерты, tutorial)
- **Настройте Budget/Alert** на $150: AWS Console → Billing → Budgets

### 2. Dedicated Host для Mac
- AWS Console → EC2 → Dedicated Hosts
- "Allocate Dedicated Host" → mac1.metal/mac2.metal
- Выберите зону (например, us-east-1a), кол-во: 1
- Host Maintenance: Disabled
- **После начала — сразу идут 24 ч аренды** (даже без instance)

### 3. Запуск Mac Instance
- EC2 Dashboard → Launch Instance
- AMI: поищите "macOS Sonoma 14.x"
- Instance Type: mac1.metal/mac2.metal
- Key Pair: создать, скачать `.pem`
- Security Group: SSH (22) + VNC (5900), Source My IP
- Advanced: Tenancy — Dedicated Host, выбрать ваш Host ID
- Launch → ждать 5–10 мин

### 4. SSH подключение
- Получить Public IPv4
- chmod 400 aws-mac-key.pem
- ssh -i aws-mac-key.pem ec2-user@YOUR_IP
- sudo /usr/bin/dscl . -passwd /Users/ec2-user

### 5. Настройка VNC
- sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.screensharing.plist
- ssh -i aws-mac-key.pem -L 5900:localhost:5900 ec2-user@YOUR_IP
- [RealVNC Viewer](https://www.realvnc.com/en/connect/download/viewer/) → localhost:5900

### 6. Xcode, инструменты, CI
- App Store → Xcode (Apple ID)
- Homebrew: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
- brew install git android-studio
- sudo gem install cocoapods

### 7. Клонирование проекта
- ssh-keygen -t ed25519 -C "your_email@example.com"
- cat ~/.ssh/id_ed25519.pub → добавить на GitHub
- git clone git@github.com:your-username/trafficban.git

### 8. Сборка Kotlin shared framework
- cd ~/trafficban
- ./gradlew :shared:linkDebugFrameworkIosSimulatorArm64
- Результат: shared.framework (iosSimulatorArm64)

### 9. Открытие/сборка в Xcode
- Xcode → Open → iosApp/iosApp.xcodeproj
- Add shared.framework (Embed & Sign)
- Add Run Script Phase: cd "$SRCROOT/.." && ./gradlew :shared:embedAndSignAppleFrameworkForXcode

### 10. Запуск iOS Simulator
- Выбрать девайс (iPhone 15 Pro)
- Cmd+R: запуск

---

## Советы по экономии
- Останавливайте instance сразу после работы, хост — только после 24 ч.
- Пример: 4 ч×день, 5 дней = $21.7/нед, $200 хватит на 2 мес+.
- После 24 ч — освободите хост (release-hosts).

## Альтернативы
- MacStadium: $79/мес
- GitHub Actions Mac: $0.08/мин. для private, бесплатно для публичных
- Mac mini (~$600)
- Codemagic: 500 мин/мес бесплатно

---

### Чеклист
- Аккаунт и кредиты AWS
- Dedicated Host и instance
- SSH и VNC готов
- Xcode установлен
- Kotlin/shared.framework собран
- Xcode+Simulator работают
- Биллинг-алерты настроены

На $200 хватит на 2 месяца по 4 ч/день!