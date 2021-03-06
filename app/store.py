from datetime import datetime
import os
import json
import base64
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from models import NewPost, Post, PostList, PostListItem, UpdatedPost
from models import Comment, CommentList, NewComment, UpdateComment
from models import UpdateUser, NewUser, User, UserList

dynamodb = boto3.client('dynamodb')

class NotFoundError(ValueError):
    pass

class ResourceAlreadyExistsError(ValueError):
    pass

class InvalidPageTokenError(ValueError):
    pass

def get_post(slug: str) -> Post:
    result = dynamodb.get_item(
        TableName=os.environ['BLOG_TABLE'],
        Key={'PK': {'S': f'P#{slug}'}, 'SK': {'S': f'P#{slug}'}},
    )
    if 'Item' not in result:
        raise NotFoundError
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
        'AuthorEmail_EntityType': {'S': f'{post.author_email}#Post'},
    }
    try:
        dynamodb.put_item(
            TableName=os.environ['BLOG_TABLE'],
            Item=item,
            ConditionExpression='attribute_not_exists(PK)', # Prevent overwriting
        )
    except ClientError as e:  
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException': 
            raise ResourceAlreadyExistsError
        else:
            raise

    return Post.from_dynamo_item(item)


def update_post(slug: str, post: UpdatedPost) -> Post:
    result = dynamodb.update_item(
        TableName=os.environ['BLOG_TABLE'],
        ReturnValues='ALL_NEW',
        Key={'PK': {'S': f'P#{slug}'}, 'SK': {'S': f'P#{slug}'}},
        UpdateExpression='SET Title=:title, AuthorEmail=:author_email, Content=:content, '
                         'UpdatedAt=:updated_at, AuthorEmail_EntityType=:author_key',
        ExpressionAttributeValues={
            ':title': {'S': post.title},
            ':author_email': {'S': post.author_email},
            ':content': {'S': post.content},
            ':updated_at': {'S': datetime.now().isoformat()},
            ':author_key': {'S': f'{post.author_email}#Post'},
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

def get_page_for_entity(entityType: str, page_token: Optional[PageToken], limit: int=20
    ) -> Tuple[List[Any], Optional[PageToken], Optional[PageToken]]:
    base_args = {
        'TableName': os.environ['BLOG_TABLE'],
        'IndexName': os.environ['BLOG_TABLE_ENTITY_INDEX'],
        'KeyConditionExpression': 'EntityType = :entity',
        'ExpressionAttributeValues': {
            ':entity': {'S': entityType}
        }
    }
    index_keys = ['PK', 'SK', 'CreatedAt', 'EntityType']
    return _get_page(base_args, index_keys, page_token, limit)

def get_page_for_author_entity(author: str, entityType: str, page_token: Optional[PageToken],
    limit: int=20) -> Tuple[List[Any], Optional[PageToken], Optional[PageToken]]:
    base_args = {
        'TableName': os.environ['BLOG_TABLE'],
        'IndexName': os.environ['BLOG_TABLE_AUTHOR_INDEX'],
        'KeyConditionExpression': 'AuthorEmail_EntityType = :key',
        'ExpressionAttributeValues': {
            ':key': {'S': f'{author}#{entityType}'}
        }
    }
    index_keys = ['PK', 'SK', 'AuthorEmail_EntityType', 'CreatedAt']
    return _get_page(base_args, index_keys, page_token, limit)

def _get_page(base_args: Dict[str, Any], index_keys: List[str], page_token: Optional[PageToken], limit: int=20
    ) -> Tuple[List[Any], Optional[PageToken], Optional[PageToken]]:
    ascending = False
    count = 0
    args = {
        **base_args,
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

    if len(results) == 0:
        return [], None, None

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
    try:
        page = PageToken.decode(pageToken) if pageToken else None
    except:
        raise InvalidPageTokenError

    items, nextToken, prevToken = get_page_for_entity('Post', page, limit=limit)

    parsed_items = [PostListItem.from_dynamo_item(item) for item in items]
    return PostList(
        posts=parsed_items,
        nextPageToken=nextToken.encode() if nextToken else None,
        prevPageToken=prevToken.encode() if prevToken else None,
    )


def create_comment(post_slug: str, comment: NewComment) -> Comment:
    created_at = datetime.now().isoformat()
    item = {
        'PK': {'S': f'P#{post_slug}'},
        'SK': {'S': f'C#{created_at}#{comment.author_email}'},
        'EntityType': {'S': 'Comment'},
        'Slug': {'S': post_slug},
        'AuthorEmail': {'S': comment.author_email},
        'Comment': {'S': comment.content},
        'CreatedAt': {'S': created_at},
        'UpdatedAt': {'S': created_at},
        'AuthorEmail_EntityType': {'S': f'{comment.author_email}#Comment'}
    }
    try:
        dynamodb.put_item(
            TableName=os.environ['BLOG_TABLE'],
            Item=item,
            ConditionExpression='attribute_not_exists(PK)', # Prevent overwriting
        )
    except ClientError as e:  
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException': 
            raise ResourceAlreadyExistsError
        else:
            raise

    return Comment.from_dynamo_item(item)

def update_comment(post_slug: str, author: str, date: datetime, comment: UpdateComment) -> Comment:
    result = dynamodb.update_item(
        TableName=os.environ['BLOG_TABLE'],
        ReturnValues='ALL_NEW',
        Key={'PK': {'S': f'P#{post_slug}'}, 'SK': {'S': f'C#{date.isoformat()}#{author}'}},
        UpdateExpression='SET Comment=:content, UpdatedAt=:updated_at',
        ExpressionAttributeValues={
            ':content': {'S': comment.content},
            ':updated_at': {'S': datetime.now().isoformat()},
        },
    )
    return Comment.from_dynamo_item(result['Attributes'])

def delete_comment(post_slug: str, author: str, date: datetime) -> None:
    dynamodb.delete_item(
        TableName=os.environ['BLOG_TABLE'],
        Key={'PK': {'S': f'P#{post_slug}'}, 'SK': {'S': f'C#{date.isoformat()}#{author}'}},
    )

def list_comments_for_post(post_slug: str, pageToken: Optional[str]=None, limit: int=20) -> CommentList:
    try:
        page = PageToken.decode(pageToken) if pageToken else None
    except:
        raise InvalidPageTokenError
    
    base_args = {
        'TableName': os.environ['BLOG_TABLE'],
        'KeyConditionExpression': 'PK = :pk AND starts_with(SK, :prefix)',
        'ExpressionAttributeValues': {
            ':pk': {'S': f'P#{post_slug}'},
            ':prefix': {'S': 'C#'}
        }
    }
    index_keys = ['PK', 'SK']
    items, nextToken, prevToken = _get_page(base_args, index_keys, page, limit)

    parsed_items = [Comment.from_dynamo_item(item) for item in items]
    return CommentList(
        comments=parsed_items,
        nextPageToken=nextToken.encode() if nextToken else None,
        prevPageToken=prevToken.encode() if prevToken else None,
    )

def list_comments(pageToken: Optional[str]=None, limit: int=20) -> CommentList:
    try:
        page = PageToken.decode(pageToken) if pageToken else None
    except:
        raise InvalidPageTokenError

    items, nextToken, prevToken = get_page_for_entity('Comment', page, limit=limit)

    parsed_items = [Comment.from_dynamo_item(item) for item in items]
    return CommentList(
        comments=parsed_items,
        nextPageToken=nextToken.encode() if nextToken else None,
        prevPageToken=prevToken.encode() if prevToken else None,
    )


def get_user(email: str) -> User:
    result = dynamodb.get_item(
        TableName=os.environ['BLOG_TABLE'],
        Key={'PK': {'S': f'U#{email}'}, 'SK': {'S': f'U#{email}'}},
    )
    if 'Item' not in result:
        raise NotFoundError

    return User.from_dynamo_item(result['Item'])

def create_user(user: NewUser) -> User:
    created_at = datetime.now().isoformat()
    item = {
        'PK': {'S': f'U#{user.email}'},
        'SK': {'S': f'U#{user.email}'},
        'EntityType': {'S': 'User'},
        'FirstName': {'S': user.first_name},
        'LastName': {'S': user.last_name},
        'Role': {'S': user.role},
        'CreatedAt': {'S': created_at},
        'UpdatedAt': {'S': created_at},
    }
    try:
        dynamodb.put_item(
            TableName=os.environ['BLOG_TABLE'],
            Item=item,
            ConditionExpression='attribute_not_exists(PK)', # Prevent overwriting
        )
    except ClientError as e:  
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException': 
            raise ResourceAlreadyExistsError
        else:
            raise

    return User.from_dynamo_item(item)

def update_user(email: str, user: UpdateUser) -> User:
    result = dynamodb.update_item(
        TableName=os.environ['BLOG_TABLE'],
        ReturnValues='ALL_NEW',
        Key={'PK': {'S': f'U#{email}'}, 'SK': {'S': f'U#{email}'}},
        UpdateExpression='SET FirstName=:first_name, LastName=:last_name, Role=:role, UpdatedAt=:updated_at',
        ExpressionAttributeValues={
            ':first_name': {'S': user.first_name},
            ':last_name': {'S': user.last_name},
            ':role': {'S': user.role},
            ':updated_at': {'S': datetime.now().isoformat()},
        },
    )
    return User.from_dynamo_item(result['Attributes'])

def delete_user(email: str):
    dynamodb.delete_item(
        TableName=os.environ['BLOG_TABLE'],
        Key={'PK': {'S': f'U#{email}'}, 'SK': {'S': f'U#{email}'}},
    )

def list_users(pageToken: Optional[str]=None, limit: int=20) -> UserList:
    try:
        page = PageToken.decode(pageToken) if pageToken else None
    except:
        raise InvalidPageTokenError

    items, nextToken, prevToken = get_page_for_entity('User', page, limit=limit)

    parsed_items = [User.from_dynamo_item(item) for item in items]
    return UserList(
        users=parsed_items,
        nextPageToken=nextToken.encode() if nextToken else None,
        prevPageToken=prevToken.encode() if prevToken else None,
    )

def list_posts_for_author(email: str, pageToken: Optional[str]=None, limit: int=20) -> PostList:
    try:
        page = PageToken.decode(pageToken) if pageToken else None
    except:
        raise InvalidPageTokenError

    items, nextToken, prevToken = get_page_for_author_entity(email, 'Post', page, limit=limit)

    parsed_items = [PostListItem.from_dynamo_item(item) for item in items]
    return PostList(
        posts=parsed_items,
        nextPageToken=nextToken.encode() if nextToken else None,
        prevPageToken=prevToken.encode() if prevToken else None,
    )

def list_comments_for_author(email: str, pageToken: Optional[str]=None, limit: int=20) -> CommentList:
    try:
        page = PageToken.decode(pageToken) if pageToken else None
    except:
        raise InvalidPageTokenError

    items, nextToken, prevToken = get_page_for_author_entity(email, 'Comment', page, limit=limit)

    parsed_items = [Comment.from_dynamo_item(item) for item in items]
    return CommentList(
        comments=parsed_items,
        nextPageToken=nextToken.encode() if nextToken else None,
        prevPageToken=prevToken.encode() if prevToken else None,
    )
