# 열차 경로 조회 웹 애플리케이션

Google Maps Platform의 Routes API(Directions API v2)를 활용하여 사용자가 입력한 출발지, 도착지, 출발 시각에 맞는 대중교통(열차 중심) 최적 경로를 조회하는 Flask 기반 웹 애플리케이션입니다.

## 주요 기능

- 출발지/도착지, 출발 시각(현지 시각), 시간대를 직접 입력하여 경로 검색
- 환승을 최소화하거나 도보를 최소화하는 등 경로 선호도 선택 가능
- Google Routes API에서 반환한 대중교통 구간(transit steps)의 노선명, 탑승/하차역, 시간 정보를 보기 좋은 형식으로 표시
- 필요 시 API 원본 응답(JSON)을 확인할 수 있는 디버깅 도구 제공

## 사전 준비

1. Google Cloud Console에서 Routes API(이전 Directions API v2)를 활성화합니다.
2. 적절한 결제 계정이 연결되어 있어야 하며, API Key를 발급받습니다.
3. 발급받은 API Key를 서버 실행 환경의 환경 변수 `GOOGLE_MAPS_API_KEY`로 설정합니다.

> **중요**: API Key는 코드 저장소에 직접 포함하지 말고 환경 변수 등 안전한 방법으로 관리하세요.

## 실행 방법

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export GOOGLE_MAPS_API_KEY="발급받은_API_KEY"
python app.py
```

서버는 기본적으로 `http://127.0.0.1:5000`에서 실행됩니다. 브라우저에서 접속하여 출발지, 도착지, 출발 일시를 입력한 뒤 **경로 조회** 버튼을 누르면 결과를 확인할 수 있습니다.

## 사용 팁

- 출발 시각은 HTML `datetime-local` 입력 형식을 따릅니다. 예: `2025-09-26T15:00`
- 시간대(Timezone)는 IANA Timezone Database 표기를 사용합니다. 예: `Asia/Seoul`
- API 응답에 따라 노선명 또는 세부 정보가 제공되지 않을 수 있습니다. 이 경우 화면에 "미제공"으로 표시됩니다.
- 동일한 조건으로 여러 번 호출하면 Google API 사용량이 증가할 수 있으니, 필요 시 응답 하단의 **API 원본 응답 보기**를 활용해 개발/디버깅을 진행하세요.

## 환경 변수

| 변수명 | 설명 |
| --- | --- |
| `GOOGLE_MAPS_API_KEY` | Google Routes API 호출에 사용되는 API Key. 필수. |
| `FLASK_SECRET_KEY` | Flask 세션/flash 메시지를 위해 사용하는 시크릿 키. 미설정 시 개발용 기본값이 사용됩니다. |

## 라이선스

본 저장소는 학습 및 데모 목적의 예제이며 별도의 라이선스를 명시하지 않았습니다. 필요에 따라 자유롭게 확장/수정해 사용하되, Google Maps Platform 서비스 약관을 준수하시기 바랍니다.
