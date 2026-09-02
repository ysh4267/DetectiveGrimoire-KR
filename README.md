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
   ├─ 한글 글자 집합 계산 ──►  Noto Sans KR Bold 서브셋 TTF
   ├─ FFDec -replace <fontId> <ttf>          (임베드 폰트 전량 교체)
   └─ FFDec -importText                      (한국어 DefineText 주입)
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

## 사용법

```bash
# 0) 사전 준비 (한 번만)
python -m pip install fonttools brotli
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

## 되돌리기

`backup/` 에 원본 SWF 67개가 그대로 있습니다.

```bash
cp -r backup/swf-dsk-original/* "<게임경로>/assets/swf-dsk/"
cp backup/DetectiveGrimoireDesktopSteam.swf "<게임경로>/"
```

Steam 라이브러리에서 **속성 → 설치된 파일 → 게임 파일 무결성 확인**을 해도
원본으로 복구됩니다.

## 라이선스 / 주의

- 게임의 텍스트·에셋 저작권은 SFB Games Ltd. 에 있습니다. 이 저장소는 **개인용
  번역 작업물**이며 비공개로 유지합니다.
- 사용 폰트: **Noto Sans KR** (SIL Open Font License 1.1)
- 도구: **JPEXS Free Flash Decompiler** (GPLv3) — 저장소에 포함하지 않고
  릴리스에서 내려받습니다.
