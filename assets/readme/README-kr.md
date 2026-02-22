<!-- 顶部标题 & 统计徽章 -->
<div align="center">
  <h1 style="margin-top: 0" align="center">Python API for JMComic</h1>

  <p align="center">
    <a href="../../README.md">简体中文</a> •
    <a href="./README-en.md">English</a> •
    <a href="./README-jp.md">日本語</a> •
    <strong>한국어</strong>
  </p>

  <p align="center">
  <strong>JMComic 접속을 위한 Python API(웹 및 모바일 지원), GitHub Actions 다운로더 통합 제공 🚀</strong>
  </p>

[![GitHub](https://img.shields.io/badge/-GitHub-181717?logo=github)](https://github.com/hect0x7)
[![Stars](https://img.shields.io/github/stars/hect0x7/JMComic-Crawler-Python?color=orange&label=stars&style=flat)](https://github.com/hect0x7/JMComic-Crawler-Python/stargazers)
[![Forks](https://img.shields.io/github/forks/hect0x7/JMComic-Crawler-Python?color=green&label=forks&style=flat)](https://github.com/hect0x7/JMComic-Crawler-Python/forks)
[![GitHub latest releases](https://img.shields.io/github/v/release/hect0x7/JMComic-Crawler-Python?color=blue&label=version)](https://github.com/hect0x7/JMComic-Crawler-Python/releases/latest)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/jmcomic?style=flat&color=hotpink)](https://pepy.tech/projects/jmcomic)
[![Licence](https://img.shields.io/github/license/hect0x7/JMComic-Crawler-Python?color=red)](https://github.com/hect0x7/JMComic-Crawler-Python)

</div>




> 이 프로젝트는 JM을 크롤링하기 위한 Python API를 캡슐화한 것입니다.
> 
> 몇 줄의 간단한 Python 코드만으로 JM의 앨범을 로컬로 원활하게 다운로드할 수 있으며, 이미지 또한 모두 처리된 상태입니다.
> 
> **안내: JM 서버의 부하를 줄이기 위해 한 번에 너무 많은 앨범을 다운로드하지 말아주세요 🙏🙏🙏**

[【가이드】튜토리얼: GitHub Actions를 사용하여 다운로드하기](../docs/sources/tutorial/1_github_actions.md)

[【가이드】튜토리얼: 즐겨찾기 데이터를 내보내고 다운로드하기](../docs/sources/tutorial/10_export_favorites.md)


![introduction.jpg](../docs/sources/images/introduction.jpg)


## 프로젝트 소개

본 프로젝트의 핵심 기능은 앨범 다운로드입니다.

이를 기반으로 사용하기 쉽고 확장성이 뛰어나며 일부 특수한 다운로드 요구를 충족할 수 있는 프레임워크가 설계되었습니다.

현재 핵심 기능은 꽤 안정적으로 동작하며, 프로젝트는 유지보수 단계에 있습니다.

다운로드 기능 외에도, 필요한 경우에 한해 추가적인 JM 인터페이스가 구현되어 있습니다. 기존 기능들은 아래와 같습니다:

- 로그인
- 앨범 검색 (모든 검색 매개변수 지원)
- 이미지 다운로드 및 복호화
- 카테고리 / 랭킹
- 앨범 / 챕터(에피소드) 세부 정보
- 개인 즐겨찾기
- 인터페이스 암호화 및 복호화 (APP API)

## 설치 가이드

> ⚠ Python이 시스템에 설치되어 있지 않다면, 다음 단계를 진행하기 전에 반드시 Python을 먼저 설치해주시기 바랍니다. 필요 버전 >= 3.7 ([Python 공식 사이트에서 다운로드하기](https://www.python.org/downloads/)).

* 공식 pip 저장소를 통한 설치 (추천. 업데이트 명령어도 동일합니다)

  ```shell
  pip install jmcomic -U
  ```
* 소스코드를 이용한 설치

  ```shell
  pip install git+https://github.com/hect0x7/JMComic-Crawler-Python
  ```

## 빠른 시작

### 1. 앨범 다운로드하기

아래의 간단한 코드를 사용하면 `JM123` 앨범의 모든 챕터 이미지를 다운로드할 수 있습니다:

```python
import jmcomic  # 이 모듈을 임포트합니다. 사전 설치 필요.
jmcomic.download_album('123')  # 다운로드하려는 앨범의 ID를 함수에 넘겨 로컬에 저장합니다.
```

위에 보이는 `download_album` 메서드는 구성 항목을 제어하는 부가적인 `option` 매개변수를 지원합니다. (예: JM 도메인, 네트워크 프록시, 이미지 포맷 변환, 플러그인 등)

사용자 환경에 맞게 이러한 구성 옵션이 필요할 수도 있습니다. 구성 파일로 옵션을 만들고 이를 사용하여 다운로드하는 것을 권장합니다. 아래의 챕터를 참고하세요:

### 2. Option 설정을 사용하여 앨범 다운로드

1. 먼저 구성 파일을 하나 만듭니다. 이름은 자율이며, 예시로 `option.yml`을 만들어보겠습니다.

   파일에는 특정한 구문 형식이 존재합니다. 문서를 참조해주세요 → [환경 설정 파일 안내](../docs/sources/option_file_syntax.md)

   한 가지 데모를 보여드리자면, 다운로드한 이미지를 png 포맷으로 변환하고 싶으시다면 `option.yml`안에 아래와 비슷한 내용을 기입하면 됩니다:

```yml
download:
  image:
    suffix: .png # 이 구성은 다운로드된 이미지를 png 로 변환하는데 쓰입니다.
```

2. 두 번째로, 아래의 Python 코드를 실행합니다.

```python
import jmcomic

# 환경 설정 객체를 생성합니다
option = jmcomic.create_option_by_file('내 설정 파일 경로, 예: D:/option.yml')
# 생성된 option 객체를 통해 앨범을 다운로드합니다
jmcomic.download_album(123, option)
# 동등한 사용법: option.download_album(123)
```

### 3. 커맨드라인 (명령줄) 사용법
> 앨범만을 다운로드 하려면 위에서 말한 방법보다 이렇게 사용하는 것이 훨씬 편하고 직관적입니다.
> 
> 예를 들어 윈도우에서는 단순하게 `Win+r` 단축키를 이용해 `jmcomic xxx` 를 타이핑하고 앨범을 즉시 내려받을 수 있습니다.

예시:

123번 앨범을 다운로드 하는 명령어

```sh
jmcomic 123
```
123번 앨범의 456번 챕터 이미지를 다운로드 하는 명령어
```sh
jmcomic 123 p456
```

커맨드라인 모드에서는 임의의 Option을 통한 커스텀 설정을 지원합니다. 환경변수나 명령어 인자를 설정할 수 있습니다:

a. 명령줄 매개변수 `--option`을 사용해 파일 경로를 지정

```sh
jmcomic 123 --option="D:/a.yml"
```

b. 환경 변수 `JM_OPTION_PATH` 를 옵션 파일명으로 설정 (권장)

> 환경 변수는 구글링을 통하거나 powershell 터미널에서 다음을 쳐서 만들 수 있습니다: `setx JM_OPTION_PATH "D:/a.yml"` 설정 후에는 다시 작동해야 적용이 됩니다.

```sh
jmcomic 123
```



## 활용법

자세한 활용 문서를 원하시면 문서 사이트로 접속하세요 → [jmcomic.readthedocs.io](https://jmcomic.readthedocs.io/zh-cn/latest)

(힌트: jmcomic은 다양한 다운로드 설정 항목을 제공합니다. 대부분의 다운로드 요구 사항과 관련된 구성 항목 및 플러그인을 쉽게 찾을 수 있을 것입니다.)

## 프로젝트의 특징

- **Cloudflare 크롤러 방지 수칙 우회**
- **금만(1.6.3) APP 인터페이스 최근의 암호화/복호화 알고리즘 완벽 지원**
- 다양한 사용 방법:

  - GitHub Actions: 웹페이지 내 바로 앨범 ID를 통하여 받을 수 있습니다. ([튜토리얼：GitHub Actions를 이용해 다운로드](../docs/sources/tutorial/1_github_actions.md))
  - 커맨드라인: 파이썬 코드를 짤 필요 없이 단순합니다. ([튜토리얼：명령줄을 이용해 다운로드](../docs/sources/tutorial/2_command_line.md))
  - Python 코드 구현: 가장 직관적이고 강력하며 최소한의 파이썬 기반 지식이 필요합니다.
- **웹 인터페이스** 및 **모바일 인터페이스** 지원. 간단한 구성을 통한 전환 지원. (**모바일 구동환경에서의 IP제한을 돌파하고 뛰어난 호환이 됩니다, 웹은 특정 지역에서 제약받지만 성능은 최고입니다.**)
- **자동 재접속(Retry) 및 도메인 전환 구조** 기본지원
- **멀티스레드 다운로드** (1이미지 당 1스레드를 통한 극단적인 빠른 스피드)
- **강력한 구성 옵션**

  - 환경 구성 없이도 매우 편하게 즐길 수 있습니다.
  - 각종 파일 포맷 종류 지원
  - 구성 가능 요소: `요청된 도메인 네임` `클라이언트 구현체` `디스크 캐시 사용 여부` `동시에 다운로드 할 파일의 개수` `포맷 바꾸기` `규칙적으로 이미지 저장하기` `요청용 메타데이터정보들(headers, cookies, proxies)` `중국어 간체/번체 변환` 등등
- **자율성 확보 (Extensible)**

  - 챕터/이미지의 다운로드 전, 다운로드 후의 콜백 기능 및 커스텀 함수 동작.
  - 여러 사용자 정의 클래스를 구성하도록 개방: `Downloader (스케줄 관리)` `Option (구성 관리)` `Client (요청 관리)` `Entity 생성` 및 등등.
  - 사용자 맞춤형 로거, 에러 감지기 시스템 
  - **강력한 'Plugin 시스템', 타인의 플러그인 이용가능, 현재 기본적으로 딸려 나오는 지원 플러그인**:
    - `로그인 플러그인`
    - `하드웨어 리소스 추적 플러그인`
    - `새로 올라온 챕터만을 받는 플러그인`
    - `압축(Archive) 지원 플러그인`
    - `클라이언트 프록시 플러그인`
    - `특정한 이미지 확장자를 지정하여 받는 플러그인`
    - `QQ메일 알리미 플러그인`
    - `로그 주제 필터 플러그인`
    - `웹 브라우저의 쿠키(Cookies)를 능동적으로 받는 플러그인`
    - `북마크 목록을 CSV 표로 추출하는 플러그인`
    - `모든 이미지를 읽기용 PDF 파일 한 개로 결합하는 플러그인`
    - `모든 이미지를 좁고 긴 하나의 원본 PNG 사진으로 결합하는 플러그인`
    - `로컬 디스크에 받은 만화를 열람할 웹서버 호스팅 플러그인`
    - `앨범 업데이트 구독 플러그인`
    - `이미지 수가 적은 챕터 건너뛰기 플러그인`
    - `중복 이미지를 탐지하고 제거하는 플러그인`
    - `경로 문자열 바꾸기 플러그인`
    - `고급 재접속(Retry) 플러그인`
    - `표지 다운로드 플러그인`

## 사용 팁

* Python 3.7 이상을 요구하지만, 라이브러리와 jmcomic 패키지의 충돌을 막기 위해 3.9 이상의 쓰임을 추천합니다.
* 여유 시간에 만들어 지는 프로젝트이기에 정보나 활용 코드의 늦은 갱신이 다분합니다. 이슈(Issue)페이지로 연락주시기 바랍니다!

## 프로젝트 폴더 안내

* `.github`: GitHub Actions 구성 파일
* `assets`: 코드가 아닌 관련 리소스
  * `docs`: 상세 가이드 및 관련 프로젝트 설명 문서
  * `option`: 설정 샘플 예제
* `src`: 실용 소스코드 폴더
  * `jmcomic`: `jmcomic` 핵심 모듈
* `tests`: 유닛 테스트 패키지 구조, 자동화 테스트
* `usage`: 실사용 시 참조하면 좋은 활용 구조

## 이하 프로젝트들에 감사드립니다.

### 이미지 복구/분할 알고리즘 & JM 모바일 API 호환

<a href="https://github.com/tonquer/JMComic-qt">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt&theme=radical" />
    <source media="(prefers-color-scheme: light)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt" />
    <img alt="Repo Card" src="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt" />
  </picture>
</a>
