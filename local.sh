set -e

export BASE_PATH=blog
export BLOG_TABLE=Blog
export BLOG_TABLE_ENTITY_INDEX=EntityType-CreatedAt-index

cd app && python api.py --host 0.0.0.0 --port 8080