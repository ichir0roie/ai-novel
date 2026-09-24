"""話に時期・場所・視点とキーテキストを足す

Revision ID: 052069310f38
Revises: 5c15aeb8dd47
Create Date: 2026-09-23 20:13:53.033965

既にある話の `text` は本文ではなく骨組み(`- 時期/場所/視点` の三行と `## 出来事`
`## 狙い`)なので、三行を列へ抜き、残りを種として `key` へ移し、`text` は空にする。

"""
from typing import Sequence, Union

import re

from alembic import op
import sqlalchemy as sa

from db.stamp import Stamp


# revision identifiers, used by Alembic.
revision: str = '052069310f38'
down_revision: Union[str, Sequence[str], None] = '5c15aeb8dd47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 話の骨組みは作中の暦の下四桁だけで「1572年」と書いてある。台帳は五桁で持つ
YEAR_OFFSET = 10000

_HEAD_RE = re.compile(r"\A(?:[ \t]*-[ \t]*(時期|場所|視点)[ \t]*:[ \t]*(.*)\n?)+", re.M)
_LINE_RE = re.compile(r"^[ \t]*-[ \t]*(時期|場所|視点)[ \t]*:[ \t]*(.*)$", re.M)

_YEAR_RE = re.compile(r"(\d+)\s*年")
_MONTH_RE = re.compile(r"(\d+)\s*月")
_DAY_RE = re.compile(r"(\d+)\s*日")
_SEASONS = (("初春", 2), ("初夏", 5), ("春", 3), ("夏", 6), ("秋", 9), ("冬", 12))


def _stamp(period: str):
    """「1586年 春」「1593年 3月25日」を台帳の整数へ。読めなければ None。"""
    year = _YEAR_RE.search(period)
    if not year:
        return None
    month = _MONTH_RE.search(period)
    if month:
        month = int(month.group(1))
    else:
        month = next((value for word, value in _SEASONS if word in period), 1)
    day = _DAY_RE.search(period)
    return Stamp(int(year.group(1)) + YEAR_OFFSET, month, int(day.group(1)) if day else 1).to_int()


def _split(text: str) -> tuple[dict, str]:
    head = _HEAD_RE.match(text or "")
    if not head:
        return {}, (text or "")
    fields = {label: value.strip() for label, value in _LINE_RE.findall(head.group(0))}
    return fields, text[head.end():].lstrip("\n")


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('episode', schema=None) as batch_op:
        batch_op.add_column(sa.Column('start', sa.BigInteger(), nullable=True, comment='話が立つ時刻'))
        batch_op.add_column(sa.Column('end', sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column('viewpoint', sa.String(), nullable=True, comment='視点。誰に寄って語るか(「ノア(十四歳)」「アウレア / ミレア」)'))
        batch_op.add_column(sa.Column('place', sa.String(), nullable=True, comment='場所。自由記述(「ヴァレンツァ 外れの川」)'))
        batch_op.add_column(sa.Column('key', sa.String(), server_default='', nullable=False, comment='キーテキスト。作者が入れる、AI 生成前の種。md では `# key` の節'))

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, text FROM episode")).fetchall()
    for row_id, text in rows:
        fields, rest = _split(text)
        connection.execute(
            sa.text("UPDATE episode SET start = :start, viewpoint = :viewpoint,"
                    " place = :place, key = :key, text = '', letters = 0 WHERE id = :id"),
            {"id": row_id,
             "start": _stamp(fields["時期"]) if fields.get("時期") else None,
             "viewpoint": fields.get("視点") or None,
             "place": fields.get("場所") or None,
             "key": rest})


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, start, viewpoint, place, key, text FROM episode")).fetchall()
    for row_id, start, viewpoint, place, key, text in rows:
        if text:
            continue
        stamp = Stamp.from_int(start) if start is not None else None
        head = [f"- 時期: {stamp.year - YEAR_OFFSET}年" if stamp else None,
                f"- 場所: {place}" if place else None,
                f"- 視点: {viewpoint}" if viewpoint else None]
        body = "\n".join(part for part in head if part)
        body = f"{body}\n\n{key}" if body and key else (body or key)
        connection.execute(
            sa.text("UPDATE episode SET text = :text, letters = :letters WHERE id = :id"),
            {"id": row_id, "text": body, "letters": len(body)})

    with op.batch_alter_table('episode', schema=None) as batch_op:
        batch_op.drop_column('key')
        batch_op.drop_column('place')
        batch_op.drop_column('viewpoint')
        batch_op.drop_column('end')
        batch_op.drop_column('start')
