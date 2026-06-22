from jmcomic import *
import os

keyword = os.getenv('SEARCH_KEYWORD', '').strip()

if not keyword:
    print('❌ 未提供搜索关键词')
    exit(1)

client = JmOption.default().new_jm_client()

print('=' * 60)
print(f'🔍 搜索关键词: {keyword}')
print('=' * 60)

page = client.search_site(search_query=keyword, page=1)

print(f'📊 共找到 {page.total} 个结果（仅显示第 1 页）')
print('=' * 60)

if page.total == 0:
    print('😕 没有找到结果，换个关键词试试')
    exit(0)

for album_id, title in page:
    print(f'🎯 [ID: {album_id}] {title}')

print('=' * 60)
print('✅ 复制上面 🎯 行的 ID 数字')
print('→ 去 "下载JM本子 (dispatch)" 工作流填入本子id 即可下载')
