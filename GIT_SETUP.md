# GitHub 프라이빗 저장소 연결

`gh` CLI 2.98.0 이 `C:\Program Files\GitHub CLI\gh.exe` 에 설치되어 있습니다.
인증은 브라우저 로그인이 필요해서 직접 한 번 실행해 주셔야 합니다.

## 1. 로그인 (한 번만)

새 터미널에서:

```powershell
gh auth login
```

- **GitHub.com** 선택
- **HTTPS** 선택
- *Authenticate Git with your GitHub credentials?* → **Yes**
- **Login with a web browser** 선택 → 표시된 8자리 코드를 브라우저에 입력

확인:

```powershell
gh auth status
```

## 2. 프라이빗 저장소 생성 + 푸시

저장소 폴더에서:

```powershell
gh repo create DetectiveGrimoire-KR --private --source=. --remote=origin --push
```

이 한 줄이 저장소 생성 · 원격 등록 · 푸시까지 처리합니다.

## 3. 이후 커밋

```powershell
git add -A
git commit -m "메시지"
git push
```

---

## 저장소에 올라가는 것 / 올라가지 않는 것

`.gitignore` 로 제외됩니다:

| 제외 대상 | 이유 |
|---|---|
| `tools/` | FFDec 20MB, 재다운로드 가능 |
| `backup/` | 원본 SWF 58MB |
| `dist/`, `work/patched/` | 빌드 산출물 |
| `work/text_raw/`, `work/decomp/`, `work/extract/` | 중간 추출물 |
| `work/fonts/*.ttf` | Noto Sans KR 6MB |

올라가는 것: 스크립트, 용어집, 번역 결과(`work/ko/*.json`), 영문 매니페스트,
문서. 약 1MB 남짓입니다.

> 게임 원문 텍스트(`work/manifest_en.json`, `work/chunks/`)가 포함되므로
> **반드시 private** 으로 유지하세요.
