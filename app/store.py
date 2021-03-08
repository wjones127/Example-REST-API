from datetime import datetime
import os
import json
import base64
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

import boto3

from models import NewPost, Post, PostList, PostListItem, UpdatedPost

dynamodb = boto3.client('dynamodb')


def get_post(slug: str) -> Post:
    result = dynamodb.get_item(
        TableName=os.environ['BLOG_TABLE'],
        Key={'PK': {'S': f'P#{slug}'}, 'SK': {'S': f'P#{slug}'}},
    )
    return Post.from_dynamo_item(result['Item'])


def create_post(post: NewPost) -> Post:
    created_at = datetime.now().isoformat()
    item = {
        'PK': {'S': f'P#{post.slug}'},
        'SK': {'S': f'P#{post.slug}'},
        'EntityType': {'S': 'Post'},
        'Slug': {'S': post.slug},
        'Title': {'S': post.title},
        'AuthorEmail': {'S': post.author_email},
        'Content': {'S': post.content},
        'CreatedAt': {'S': created_at},
        'UpdatedAt': {'S': created_at},
    }
    dynamodb.put_item(
        TableName=os.environ['BLOG_TABLE'],
        Item=item,
        ConditionExpression='attribute_not_exists(PK)', # Prevent overwriting
    )
    return Post.from_dynamo_item(item)


def update_post(slug: str, post: UpdatedPost) -> Post:
    result = dynamodb.update_item(
        TableName=os.environ['BLOG_TABLE'],
        ReturnValues='ALL_NEW',
        Key={'PK': {'S': f'P#{slug}'}, 'SK': {'S': f'P#{slug}'}},
        UpdateExpression='SET Title=:title, AuthorEmail=:author_email, Content=:content, UpdatedAt=:updated_at',
        ExpressionAttributeValues={
            ':title': {'S': post.title},
            ':author_email': {'S': post.author_email},
            ':content': {'S': post.content},
            ':updated_at': {'S': datetime.now().isoformat()},
        },
    )
    return Post.from_dynamo_item(result['Attributes'])


def delete_post(slug: str):
    dynamodb.delete_item(
        TableName=os.environ['BLOG_TABLE'],
        Key={'PK': {'S': f'P#{slug}'}, 'SK': {'S': f'P#{slug}'}},
    )


class PageToken(NamedTuple):
    last_evaluated_key: Dict
    scan_forward: bool

    @classmethod
    def decode(cls, token: str) -> 'PageToken':
        data = json.loads(base64.b64decode(token.encode()).decode())
        return cls(data['last_evaluated_key'], data['scan_forward'])

    def encode(self) -> str:
        data = self._asdict()
        return base64.b64encode(json.dumps(data).encode()).decode()


def get_page(entityType: str, page_token: Optional[PageToken], limit: int=20
    ) -> Tuple[List[Any], Optional[PageToken], Optional[PageToken]]:
    ascending = False
    count = 0
    args = {
        'TableName': os.environ['BLOG_TABLE'],
        'IndexName': os.environ['BLOG_TABLE_ENTITY_INDEX'],
        'KeyConditionExpression': 'EntityType = :entity',
        'ExpressionAttributeValues': {
            ':entity': {'S': entityType}
        },
        'ScanIndexForward': page_token.scan_forward if page_token else ascending,
        # only way to know if there are more results is to get an extra item
        'Limit': limit + 1, 
    }
    if page_token and page_token.last_evaluated_key:
        args['ExclusiveStartKey'] = page_token.last_evaluated_key
    
    results = []
    while True:
        response = dynamodb.query(**args)
        results.extend(response['Items'])
        count += len(response['Items'])
        if count >= limit:
            break
        elif 'LastEvaluatedKey' not in response:
            break
        else:
            args['Limit'] = limit - count
            args['ExclusiveStartKey'] = response['LastEvaluatedKey']

    index_keys = ['PK', 'SK', 'CreatedAt', 'EntityType']
    if not page_token or page_token.scan_forward == ascending:
        hasMoreItemsNext = len(results) > limit
        hasMoreItemsPrev = page_token is not None
    else:
        hasMoreItemsNext = page_token is not None
        hasMoreItemsPrev = len(results) > limit
    
    if not page_token or page_token.scan_forward == ascending:
        results = results[:limit]
    else:
        # If we go to previous page, DynamoDB scans opposite of sort direction
        results = list(reversed(results[:limit]))

    lastKeyNext = {key: results[-1][key] for key in index_keys}
    lastKeyPrev = {key: results[0][key] for key in index_keys}
    nextPageToken = PageToken(lastKeyNext, ascending) if hasMoreItemsNext else None
    prevPageToken = PageToken(lastKeyPrev, not ascending) if hasMoreItemsPrev else None

    return results, nextPageToken, prevPageToken


def list_posts(pageToken: Optional[str] = None, limit: int = 2) -> PostList:
    page = PageToken.decode(pageToken) if pageToken else None

    items, nextToken, prevToken = get_page('Post', page, limit=limit)

    parsed_items = [PostListItem.from_dynamo_item(item) for item in items]
    return PostList(
        posts=parsed_items,
        nextPageToken=nextToken.encode() if nextToken else None,
        prevPageToken=prevToken.encode() if prevToken else None,
    )

