# Detective Grimoire 한글패치

Steam판 **Detective Grimoire** (SFB Games, 2014 / Adobe AIR)의 한국어 패치와
그 패치를 만들어내는 도구 모음입니다.

## 게임이 텍스트를 저장하는 방식

리버스 엔지니어링으로 확인한 구조입니다.

| 위치 | 내용 | 분량 |
|---|---|---|
| `assets/swf-dsk/**/*.swf` 의 **DefineText** 태그 | 화면에 보이는 거의 모든 대사·단서·메뉴 | 3,278 태그 / 21,144 단어 |
| 메인 SWF `DetectiveGrimoireDesktopSteam.swf` 의 **ABC 상수 풀** | 추리 미니게임 문장 조각, 확인 대화상자 | 103 문자열 |
| 각 SWF 의 **DefineFont2/3** | 서브셋된 임베드 폰트 (원문에 쓰인 글자만 포함) | SWF당 1~3개 |
| 일부 UI (`SLOT`, `TAP TO CREATE NEW SAVE FILE` 등) | **벡터 도형으로 그려진 그림** | 번역 불가 |

`assets/xml/` 은 TexturePacker 아틀라스이고, `assets/mp3/` 파일명은 음성 클립
ID입니다. 둘 다 화면 텍스트를 담고 있지 않습니다.

### AIR 무결성

`META-INF/signatures.xml` 이 에셋 949개를 포함해 서명하고 있지만, 캡티브 런타임
빌드는 실행 시 이를 검증하지 않습니다. 에셋 SWF를 수정한 뒤 정상 실행되는 것을
확인했습니다.

## 패치 파이프라인

```
원본 SWF
   │
   ├─ FFDec -export text  ──►  work/text_raw/**/texts/*.txt   (text:formatted)
   │                              └─ 번역 청크 work/chunks/*.json
   │                                    └─ 번역 결과 work/ko/*.json
   │
   ├─ 한글 글자 집합 계산 ──►  Noto Sans KR Bold 서브셋 TTF  (윤곽 겹침 제거된 것)
   ├─ FFDec -replace <fontId> <ttf>          (임베드 폰트 전량 교체)
   ├─ FFDec -importText                      (한국어 DefineText 주입)
   └─ fixadvances.py                         (글리프 어드밴스 실측값으로 재작성 + 자간)
             │
             └──►  dist/assets/swf-dsk/**/*.swf

메인 SWF ── ABC 상수 풀 문자열 교체 (work/abcpatch.py) ──► dist/*.swf
```

### 핵심 주의사항

- **FFDec `-importText` 은 `<폴더>/texts/*.txt` 구조를 요구합니다.** 폴더를 바로
  주면 조용히 아무 것도 하지 않고 성공한 것처럼 종료합니다.
- **`text:formatted` 파일은 반드시 CRLF** 여야 합니다. LF면 헤더 블록이 파싱되지
  않고 `[xmin 23 ...]` 가 화면에 그대로 출력됩니다.
- 임베드 폰트는 **서브셋**이라 원문에 없던 글자는 조용히 사라집니다. 한글을 넣기
  전에 반드시 폰트를 먼저 교체해야 합니다.
- `spacing` / `spacingpair` (커닝) 줄은 원문 글자를 참조하므로 재작성 시 제거합니다.
- ABC는 문자열을 **인덱스로만** 참조하므로, 개수와 순서만 지키면 문자열 테이블을
  통째로 다시 써도 안전합니다. (무변경 왕복이 바이트 단위로 일치함을 확인)

## 레이아웃 보정

원문 좌표를 그대로 쓰면 한글이 깨집니다. `patch_swf.py` 가 세 가지를 보정합니다.

| 문제 | 보정 |
|---|---|
| 줄이 단어 중간에서 끊김 | `wrap_lines` — 어절 경계에서 균형 잡힌 DP 줄바꿈 |
| 교체 폰트가 원본보다 ~12% 넓어 크레딧 등이 잘림 | `fit_scale` — 원본 `TextBounds` 에 맞게 글자 크기 축소(하한 0.72) |
| 레코드 `x` 가 영문 폭 기준이라 정렬이 들쭉날쭉 | `realign` — 가운데 정렬 블록은 bounds 중앙 기준으로 재계산 |

`record_lines()` 가 뒤 두 가지의 전제입니다. **하나의 DefineText가 한 줄에 여러
레코드를 둘 수 있습니다** (이름표가 `"OFFICER " + "JAMES"` 로 쪼개져 있음).
이를 각각 다른 줄로 취급하면 `제임스` 위에 `경관` 이 겹쳐 찍힙니다.

## 글자가 겹치고 획에 선이 보이던 문제

첫 빌드에서 한글이 서로 붙고, 글자 안에 얇은 경계선이 보였습니다. 원인이 둘이었습니다.

### ① 자간 — 폰트에 어드밴스 테이블이 없다

게임의 `DefineFont3` 은 전부 **`FontFlagsHasLayout = 0`** 입니다. 원래 영문 텍스트는
Flash Pro가 저작 시점에 각 `DefineText` 안에 어드밴스를 직접 박아넣었기 때문에
폰트에 메트릭이 없어도 됐습니다. 그래서 FFDec가 새 글자를 넣을 때 참고할 값이 없고,
모르는 글리프에는 **상수를 추정**해 넣습니다.

`ClueGraphic` 실측 (본문 높이 600 twips 기준):

| | 어드밴스 | em 환산 |
|---|---|---|
| Noto Sans KR 한글 실제 값 | 552 | 0.920 em |
| FFDec가 넣은 값 | 467 | 0.778 em |
| 글리프 잉크 폭 | 518 | 0.864 em |

어드밴스가 잉크 폭보다 **51 twips 좁아서**, 옆 글자와 물리적으로 겹치고 있었습니다.

`fixadvances.py` 가 `-importText` 뒤에 붙어서, `DefineFont3` 의 CodeTable로
글리프 인덱스 → 문자를 되짚고 폰트의 실제 어드밴스로 전부 다시 씁니다.
`TextBounds` 도 같이 넓힙니다. `patch_swf.TRACKING` (기본 `0.045` em) 이 여기에 더해집니다.

> `DefineText` 비트 패킹은 원본 617개 태그를 파싱 → 재작성 → 재파싱해 **전부 바이트 일치**함을 확인했습니다.

### ② 획 안의 선 — 겹친 윤곽선

가변폰트를 `instantiateVariableFont` 로 정적화하면 **윤곽선이 겹친 채** 남습니다.
한글 한 글자가 자소별 윤곽 4~8개로 이뤄지고 서로 교차합니다. 일반 렌더러는
non-zero winding으로 처리해 티가 안 나지만, SWF는 각 edge에 좌/우 fill을 명시하는
방식이라 **교차 지점이 전부 얇은 선으로 드러납니다.**

`mkfont.py` 에서 `skia-pathops` 기반 `removeOverlaps` 로 미리 합칩니다
(예: `관` 윤곽 8개 → 4개, `명` 7개 → 5개).

## ABC 문자열의 함정

메인 SWF의 상수 풀 문자열은 **인덱스로만** 참조되므로, 하나를 바꾸면 그 문자열의
모든 용처가 함께 바뀝니다. 그런데 일부는 기계용 식별자를 겸합니다.

- `DataItem.name` → `DataList._nameLookup` 의 키, `byName("cogs")` 같은 리터럴
- `char.name` → 오디오 경로에 그대로 들어감: `"surprised/" + name + "/x.mp3"`
- `area.name` → MovieClip 프레임 레이블 `gotoAndStop(area.name)`, 자식 조회 키

`abc_safety.py` 가 이런 문자열 11개(`Harper`, `Sally Spears`, `Intro` 등)를
차단합니다. 번역했다면 음성이 조용히 로드되지 않고 장소 화면이 깨졌을 것입니다.

## 번역되지 않는 부분 (원리상 불가)

| 대상 | 이유 |
|---|---|
| `SLOT`, `CHALLENGES`, `TAP TO CREATE NEW SAVE FILE`, `BACK TO MENU`, `Area: SWAMP DOCK`, `PLAY` / `OPTIONS` / `ACHIEVEMENTS` / `QUIT` / `CREDITS` | 텍스트가 아니라 **벡터 도형으로 그려진 그림**. 다시 그려야 함 |
| 인트로·엔딩 등 컷신 | `assets/mp4-720/*.mp4` 로 **사전 렌더링된 영상**. 영상 편집 필요 |
| 제작진 이름 | 실명이라 그대로 둠 (역할 이름만 번역) |

## 사용법

```bash
# 0) 사전 준비 (한 번만)
python -m pip install fonttools brotli skia-pathops
#    tools/ffdec/ 에 JPEXS FFDec 26.2.1 배치
python work/mkfont.py                # Noto Sans KR Bold 정적 폰트 생성

# 1) 원문 추출
python work/extract_all.py
python work/build_manifest.py
python work/make_chunks.py

# 2) 번역  ->  work/ko/*.json   (id -> 한국어 문자열)

# 3) 빌드
python work/build.py                 # dist/ 에 결과 생성
python work/build.py --install       # 게임에 바로 설치

# 4) 검수
python work/check_fit.py --json work/overflow.json   # 말풍선 넘침 검사
```

## 검증 결과

빌드 산출물 기준:

- 에셋 SWF **44개** 패치, **글리프 누락 0건**
- 메인 SWF 상수 풀 **8,190개 유지**, 한국어 **92개 전부 삽입**, 영문 원문 **0개 잔존**,
  식별자 **11개 그대로**
- 여러 줄 단서 텍스트 **275줄 전부 중앙 정렬 오차 0**

실제 플레이 확인:

| 화면 | 결과 |
|---|---|
| 타이틀 / 저장 슬롯 | 「저장 파일을 선택하세요.」 정상 |
| 헤드폰 안내 | 정상 |
| 인트로 대사 (그리모어) | 말풍선 안 4줄 중앙 정렬 정상 |
| 화자 이름표 | 「그리모어」 · 「제임스 경관」 정상 (겹침 수정 완료) |
| 경찰 파일 단서 | 4개 문단 전부 정상 |
| 종료 확인 대화상자 | 「정말 게임을 / 종료하시겠습니까?」 + 「예 / 아니요」 정상 |
| 크레딧 | 잘림 해소 |

## 되돌리기

`backup/` 에 원본 SWF 67개가 그대로 있습니다.

```bash
cp -r backup/swf-dsk-original/* "<게임경로>/assets/swf-dsk/"
cp backup/DetectiveGrimoireDesktopSteam.swf "<게임경로>/"
```

Steam 라이브러리에서 **속성 → 설치된 파일 → 게임 파일 무결성 확인**을 해도
원본으로 복구됩니다.

세이브 파일은 게임 폴더가 아니라 아래에 있어 패치와 무관합니다. 테스트 전
`backup/saves/` 에 복사해 두었습니다.

```
%APPDATA%\air.com.sfbgames.DetectiveGrimoire\Local Store\#SharedObjects\DetectiveGrimoireDesktopSteam.swf\DetectiveGrimoireSave.sol
```

## 라이선스 / 주의

- 게임의 텍스트·에셋 저작권은 SFB Games Ltd. 에 있습니다. 이 저장소는 **개인용
  번역 작업물**이며 비공개로 유지합니다.
- 사용 폰트: **Noto Sans KR** (SIL Open Font License 1.1)
- 도구: **JPEXS Free Flash Decompiler** (GPLv3) — 저장소에 포함하지 않고
  릴리스에서 내려받습니다.
