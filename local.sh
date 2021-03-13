set -e

export BASE_PATH=blog
export BLOG_TABLE=BlogV2
export BLOG_TABLE_ENTITY_INDEX=EntityType-CreatedAt-Index
export BLOG_TABLE_AUTHOR_INDEX=AuthorEmail_EntityType-CreatedAt-IndexV2

cd app && python api.py --host 0.0.0.0 --port 8080