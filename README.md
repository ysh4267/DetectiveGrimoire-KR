# Detective Grimoire 한글패치

Steam판 **Detective Grimoire** (SFB Games, 2014) 의 한국어 패치입니다.
대사·단서·인물 정보·메뉴까지 **3,278개 텍스트, 21,144단어**를 번역했습니다.

> ⚠️ 게임을 **정식 구매**하신 분만 사용하실 수 있습니다.
> 이 저장소에는 게임 파일이 들어 있지 않습니다. 패치는 원본과의 *차이*만
> 담고 있어서, 게임이 없으면 아무 소용이 없습니다.

---

## 설치

1. [Releases](../../releases) 에서 `DetectiveGrimoire-KR-Patch.exe` 를 받습니다.
2. **게임 폴더**에 넣습니다. `Detective Grimoire.exe` 가 있는 그 폴더입니다.
   - Steam → 라이브러리 → Detective Grimoire 우클릭 → **관리 → 로컬 파일 보기**
   - 보통 `...\steamapps\common\Detective Grimoire\`
3. 받은 exe 를 **실행**하고 `1` 을 누릅니다.

끝입니다. 게임을 켜면 한국어로 나옵니다.

```
==========================================================
  Detective Grimoire 한글패치
==========================================================

게임 폴더: ...\steamapps\common\Detective Grimoire
패치 데이터: 45개 파일

  1) 한글패치 적용
  2) 원본으로 되돌리기
  3) 열리지 않는 세이브 슬롯 고치기
  0) 닫기
```

명령줄로도 됩니다: `DetectiveGrimoire-KR-Patch.exe --apply` / `--restore` / `--fix-save`

## 되돌리기

같은 exe 를 실행하고 `2` 를 누르면 됩니다. 패치할 때 원본을 게임 폴더의
`backup_kr_patch\` 에 복사해 두므로 언제든 복구됩니다.

Steam에서 **속성 → 설치된 파일 → 게임 파일 무결성 확인** 을 돌려도 원본으로
돌아갑니다.

## 세이브 슬롯이 눌러도 안 열릴 때

**패치와 무관한 원본 게임의 버그입니다.** 원본 파일로 되돌려도 똑같이 재현됩니다.

게임은 세이브를 불러올 때 이렇게 합니다.

```actionscript
Area(GameData.areaList.byID(saveData.areaCurrent)).screen
```

`areaCurrent` 는 −1 로 시작해서, 플레이어가 실제로 어떤 장소에 들어가야 진짜
번호로 바뀝니다. 그 전에 — 즉 **인트로 도중에** — 게임이 꺼지면 자동저장이
−1 을 기록합니다. 다시 켜서 그 슬롯을 누르면 `byID(-1)` 이 아무것도 돌려주지
않아 예외가 나고, 게임이 그 예외를 조용히 삼킵니다. **슬롯 정보는 멀쩡히
보이는데 눌러도 아무 일도 일어나지 않습니다.**

patcher 메뉴에서 `3` 을 누르면 고쳐집니다. 세이브는 `.bak` 으로 백업됩니다.

## 번역되지 않는 부분

| 대상 | 이유 |
|---|---|
| `SLOT`, `PLAY`, `TAP TO CREATE NEW SAVE FILE`, `BACK TO MENU`, `Area: SWAMP DOCK` 등 | 텍스트가 아니라 **벡터 도형으로 그려진 그림**입니다. 다시 그려야 합니다 |
| 인트로·엔딩 컷신 | `assets/mp4-720/*.mp4` 로 **사전 렌더링된 영상**입니다 |
| 제작진 이름, 저작권 문구 | 실명·법적 고지라 원문 그대로 둡니다 |

## 동작 방식

패치 파일에는 게임 에셋이 들어 있지 않습니다. 원본 SWF를 **사전(dictionary)으로
쓴 zstd 델타**만 담깁니다. SWF 용량의 대부분은 번역이 건드리지 않는 그림이라,
49MB 분량이 **2.5MB** 로 줄어듭니다.

```
원본 SWF (사용자 PC)  ──┐
                        ├─► zstd 델타 복원 ─► 한글 SWF
patch 델타 (2.5MB)  ────┘
```

적용 전에 원본의 SHA-256을, 적용 후에 결과의 SHA-256을 확인합니다. 하나라도
어긋나면 아무것도 쓰지 않고 멈춥니다.

---

# 개발자용

## 게임이 텍스트를 저장하는 방식

| 위치 | 내용 | 분량 |
|---|---|---|
| `assets/swf-dsk/**/*.swf` 의 **DefineText** | 화면에 보이는 거의 모든 대사·단서·메뉴 | 3,278 태그 |
| 메인 SWF 의 **ABC 상수 풀** | 추리 미니게임 문장 조각, 확인 대화상자 | 103 문자열 |
| 각 SWF 의 **DefineFont2/3** | 서브셋된 임베드 폰트 (원문에 쓰인 글자만) | SWF당 1~3개 |

`assets/xml/` 은 TexturePacker 아틀라스, `assets/mp3/` 파일명은 음성 클립 ID라
화면 텍스트가 없습니다.

**AIR 무결성** — `META-INF/signatures.xml` 이 에셋 949개를 서명하지만, 캡티브
런타임 빌드는 실행 시 검증하지 않습니다.

## 파이프라인

```
원본 SWF
   ├─ FFDec -export text  ──►  work/text_raw/**/texts/*.txt   (text:formatted)
   │                              └─ work/chunks/*.json ─► 번역 ─► work/ko/*.json
   ├─ 글자 집합 계산 ──►  Noto Sans KR Bold 서브셋 (윤곽 겹침 제거)
   ├─ FFDec -replace <fontId> <ttf>
   ├─ FFDec -importText
   └─ fixadvances.py            (글리프 어드밴스 실측값 재작성 + 자간)
             └──►  dist/  ──►  makepatch.py  ──►  release/*.dgpatch
```

```bash
python -m pip install fonttools brotli skia-pathops zstandard pyinstaller
# tools/ffdec/ 에 JPEXS FFDec 26.2.1 배치

python work/mkfont.py          # 한글 베이스 폰트
python work/extract_all.py     # 원문 추출 (본인 게임에서)
python work/build_manifest.py
python work/make_chunks.py
#   -> 번역 -> work/ko/*.json
python work/build.py           # dist/ 생성
python work/build.py --install # 게임에 바로 설치
python work/makepatch.py       # 배포용 .dgpatch
python patcher/build_exe.py    # 배포용 exe
```

## 함정 다섯 가지

**1. FFDec `-importText` 은 `<폴더>/texts/*.txt` 구조를 요구합니다.**
폴더를 바로 주면 아무 것도 하지 않고 성공한 것처럼 종료합니다.

**2. `text:formatted` 파일은 반드시 CRLF** 여야 합니다. LF면 헤더가 파싱되지
않고 `[xmin 23 ...]` 가 화면에 그대로 출력됩니다.

**3. 폰트에 어드밴스 테이블이 없습니다.** 이 게임의 `DefineFont3` 은 전부
`FontFlagsHasLayout = 0` 입니다. 영문은 Flash Pro가 저작 시점에 어드밴스를 각
`DefineText` 안에 박아넣어서 폰트 메트릭이 필요 없었습니다. 그래서 FFDec가 새
글자를 넣을 때 잴 기준이 없어 **상수를 추정**합니다.

| (본문 높이 600 twips) | 어드밴스 | em |
|---|---|---|
| Noto Sans KR 한글 실제 | 552 | 0.920 |
| FFDec가 넣은 값 | 467 | 0.778 |
| 글리프 잉크 폭 | 518 | 0.864 |

잉크보다 51 twips 좁아서 옆 글자와 **물리적으로 겹칩니다.** `fixadvances.py` 가
`DefineFont3` 의 CodeTable로 글리프→문자를 되짚어 전부 다시 씁니다.
(원본 617개 태그를 파싱→재작성→재파싱해 바이트 일치 확인)

**4. 가변폰트 정적화는 윤곽선을 겹친 채로 남깁니다.** 한글 한 글자가 자소별
윤곽 4~8개로 교차하는데, SWF는 각 edge에 좌/우 fill을 명시하는 방식이라
**교차 지점이 전부 얇은 선으로 드러납니다.** `skia-pathops` 로 미리 합칩니다.

**5. ABC 문자열은 인덱스로만 참조됩니다.** 하나를 바꾸면 모든 용처가 함께
바뀌는데, 일부는 기계용 식별자를 겸합니다.

- `DataItem.name` → `DataList._nameLookup` 키, `byName("cogs")` 리터럴
- `char.name` → 오디오 경로: `"surprised/" + name + "/x.mp3"`
- `area.name` → MovieClip 프레임 레이블 `gotoAndStop(area.name)`

`abc_safety.py` 가 이런 문자열 11개(`Harper`, `Sally Spears`, `Intro` 등)를
차단합니다. 번역했다면 음성이 조용히 안 나오고 장소 화면이 깨졌을 겁니다.

## 레이아웃 보정

| 문제 | 보정 |
|---|---|
| 줄이 단어 중간에서 끊김 | `wrap_lines` — 어절 경계 균형 DP |
| 교체 폰트가 ~12% 넓어 크레딧이 잘림 | `fit_scale` — `TextBounds` 에 맞게 축소(하한 0.72) |
| 레코드 `x` 가 영문 폭 기준이라 정렬이 들쭉날쭉 | `realign` — bounds 중앙 기준 재계산 |
| 한글이 세로로 커서 윗줄과 부딪힘 | `vfit_scale` — 줄 간 잉크 충돌 검사 |

`record_lines()` 가 전제입니다. **하나의 DefineText가 한 줄에 여러 레코드를 둘
수 있습니다** (이름표가 `"OFFICER " + "JAMES"`). 각각 다른 줄로 취급하면
`제임스` 위에 `경관` 이 겹쳐 찍힙니다.

`vfit_scale` 은 절대 기준이 아니라 **원문 대비 증가분**만 봅니다. 크레딧 일부는
1080 twips 글자를 680 twips 행간에 얹는 원래부터 빡빡한 설계라, 절대 기준으로
재면 손대지도 않은 영문 이름까지 하한까지 줄어듭니다.

## 저장소에 없는 것

게임 원문 스크립트(`work/manifest_en.json`, `work/chunks/*.json`)는 저작권이
SFB Games Ltd. 에 있어 포함하지 않았습니다. 게임을 갖고 계시면
`extract_all.py` → `build_manifest.py` → `make_chunks.py` 로 본인 설치본에서
직접 뽑을 수 있습니다.

## 라이선스

- 도구·스크립트: MIT
- 번역문(`work/ko/`): 2차 저작물. 개인적 사용에 한합니다
- 게임의 텍스트·에셋 저작권: **SFB Games Ltd.**
- 폰트: **Noto Sans KR** (SIL Open Font License 1.1)
- **JPEXS Free Flash Decompiler** (GPLv3) — 포함하지 않고 릴리스에서 받습니다

이 프로젝트는 SFB Games 와 무관한 팬 제작물입니다. 권리자의 요청이 있으면
즉시 내리겠습니다.
