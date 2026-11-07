# Лабораторная работа №4: Защищённый API модели, веб-интерфейс и мониторинг

## Схема запросов и способы доступа

### Эндпоинты API

| Метод | Путь | Описание | Аутентификация |
|-------|------|----------|----------------|
| GET | `/` | Веб-интерфейс для отправки запросов | Нет |
| GET | `/health` | Проверка готовности сервиса | Нет |
| POST | `/predict` | Предсказание класса DNS-трафика | `X-API-Token` |
| GET | `/metrics` | Метрики Prometheus | `X-API-Token` |

### Схема запроса `POST /predict`

**Заголовок:**

Content-Type: application/json
X-API-Token: <your-api-token>

**Тело запроса:**
```json
{
  "rows": [
    {
      "src_port": 53,
      "dst_port": 443,
      "duration": 1.0,
      "total_bytes": 100,
      "receiving_bytes": 50,
      "sending_bytes": 50,
      "packets_rate": 2.0,
      "packets_len_rate": 100.0,
      "min_packets_len": 20,
      "max_packets_len": 80,
      "mean_packets_len": 50.0,
      "standard_deviation_packets_len": 10.0,
      "variance_packets_len": 100.0,
      "coefficient_of_variation_packets_len": 0.2,
      "dns_domain_name_length": 20,
      "dns_subdomain_name_length": 10,
      "numerical_percentage": 0.1,
      "character_entropy": 2.5,
      "max_continuous_numeric_len": 2,
      "max_continuous_alphabet_len": 5,
      "max_continuous_consonants_len": 3,
      "max_continuous_same_alphabet_len": 2,
      "vowels_consonant_ratio": 0.5,
      "conv_freq_vowels_consonants": 0.4,
      "distinct_ttl_values": 1,
      "ttl_values_min": 64,
      "ttl_values_max": 64,
      "ttl_values_mean": 64.0,
      "ttl_values_mode": 64,
      "ttl_values_median": 64,
      "distinct_A_records": 1
    }
  ]
}
```
*Пример ответа (успех, HTTP 200):*
{
  "prediction": [0],
  "model_version": "9a98d9820bf7",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}

*Пример ответа /health (готов, HTTP 200):*
{
  "status": "healthy",
  "model_version": "9a98d9820bf7"
}

*Пример ответа /health (не готов, HTTP 503):*
{
  "status": "not_ready"
}

## Запуск и воспроизведение сценария

### Запуск сервиса

**Через Docker:**
```bash
# 1. Сборка образа
docker build -t dns-tunneling-detector:lab4 .

#2. Запуск контейнера (токен передаётся через переменную окружения)
docker run -d --name dns-api \
  -p 8000:8000 \
  -e API_TOKEN="demo-token" \
  dns-tunneling-detector:lab4

# 3. Проверка готовности
curl -s http://localhost:8000/health | python3 -m json.tool

# 4. Проверка запуска от непривилегированного пользователя
docker exec dns-api id -u
```

**Запуск через uvicorn**

Для локальной разработки без Docker можно запустить приложение напрямую через `uvicorn`.

```bash
#1. Активация виртуального окружения:
source .venv/bin/activate

#2. Установка зависимостей:
pip install -r requirements.txt

#3. Запуск приложения:
export API_TOKEN="your-secure-token"
uvicorn src.api:app --host 127.0.0.1 --port 8000 --reload
```

## Лимиты и ограничения

### Лимиты и ограничения

| Параметр | Значение | Обоснование |
|----------|----------|-------------|
| Максимальный размер тела запроса | 2 МБ | Защита от DoS через переполнение памяти; проверка выполняется потоково до полной загрузки в память |
| Максимальное количество строк в `/predict` | 10 000 | Ограничение объёма вычислений для одного запроса |
| Rate limiting | 20 запросов в минуту на IP | Защита от брутфорса токена и злоупотреблений; реализовано скользящим окном в `InMemoryRateLimiter` |
| Таймаут выполнения предсказания | 10 секунд | Освобождение ресурсов при зависании инференса; фоновая задача корректно завершается |
| Таймаут ожидания в очереди | 1 секунда | Быстрый отказ при перегрузке сервиса (HTTP 503) |
| Максимум параллельных предсказаний | 2 | Контроль нагрузки на модель через `asyncio.Semaphore` |
| Пользователь контейнера | UID 10001 (не root) | Принцип наименьших привилегий; снижение рисков при компрометации контейнера |
| Количество признаков на строку | 31 (фиксированная схема) | Соответствие обучающей выборке; защита от подмены признаков |
| Допустимые типы значений | `int`, `float` (без `bool`, `NaN`, `Inf`) | Защита от некорректных данных и переполнения при приведении к `float32` |


## Воспроизведение сценария обнаружения

Сценарий имитирует подбор API-токена и демонстрирует реакцию системы: рост счётчиков отказов в метриках Prometheus и появление структурированных записей в логах. Токен и содержимое запросов в логи не попадают.

### Шаг 1. Фиксация нормального состояния

Проверяем, что сервис готов и принимает корректные запросы:
```bash
curl -s -H "X-API-Token: demo-token" http://localhost:8000/health
```
Ожидаемый ответ: `{"status":"healthy","model_version":"9a98d9820bf7"}`.

Фиксируем начальное значение счётчика отказов:

```bash
curl -s -H "X-API-Token: demo-token" http://localhost:8000/metrics \
  | grep 'dns_api_requests_total{method="POST",route="/predict",status="401"}'
```
### Шаг 2. Генерация аномальной активности

Отправляем серию из 5 запросов с заведомо неверным токеном:

```bash
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -w "Запрос $i: HTTP %{http_code}\n" \
    -X POST http://localhost:8000/predict \
    -H "X-API-Token: wrong-token" \
    -H "Content-Type: application/json" \
    -d '{"rows":[]}'
done
```
Ожидаемый результат: 5 ответов со статусом HTTP 401

### Шаг 3. Анализ метрик и логов

Проверяем рост счётчика отказов:

```bash
curl -s -H "X-API-Token: demo-token" http://localhost:8000/metrics \
  | grep 'dns_api_requests_total{method="POST",route="/predict",status="401"}'
```
Значение счётчика должно увеличиться на 5.

Просматриваем структурированные логи (токен и содержимое запроса не попадают в логи):

```bash
docker logs --tail 30 dns-api 2>&1 \
  | grep '"refusal_type": "authentication"'
```
