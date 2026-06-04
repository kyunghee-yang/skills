import os
import sys

src_path = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, src_path)

import pytest

from fixtures import build_sample_receipts, build_sample_xls


@pytest.fixture(scope="session")
def sample_xls(tmp_path_factory):
    """합성 승인내역 .xls 경로. 세션 1회 생성하여 모든 테스트가 공유한다.

    원작성자 로컬 경로 의존을 제거하기 위한 재현 가능 픽스처.
    """
    path = tmp_path_factory.mktemp("xls") / "간편서비스_승인내역.xls"
    return build_sample_xls(str(path))


@pytest.fixture(scope="session")
def sample_receipts_dir(tmp_path_factory):
    """합성 영수증 이미지 3장이 든 폴더 경로. 이름순 정렬·확장자 필터 검증용."""
    folder = tmp_path_factory.mktemp("receipts")
    build_sample_receipts(str(folder), count=3)
    return str(folder)
