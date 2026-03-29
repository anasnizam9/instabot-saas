"""
Phase 2 Tests: Instagram OAuth, Account Management, and Post Scheduling
"""

import pytest
from datetime import datetime, timedelta, UTC
from httpx import AsyncClient, HTTPStatusError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Organization, OrganizationMember, InstagramAccount, ScheduledPost
from app.schemas.instagram import ScheduledPostStatus
from app.core.vault import vault


@pytest.mark.asyncio
async def test_instagram_oauth_redirect_url(client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession):
    """Test OAuth redirect URL generation with state parameter"""
    user, org = user_with_org

    response = await client.post(
        "/api/v1/instagram/oauth/redirect-url",
        json={"organization_id": org.id},
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "auth_url" in data
    assert "api.instagram.com" in data["auth_url"]
    assert f"state={org.id}" in data["auth_url"]


@pytest.mark.asyncio
async def test_instagram_account_connect_via_oauth_callback(
    client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession
):
    """Test OAuth callback creates InstagramAccount with encrypted token"""
    user, org = user_with_org

    # In test mode this calls the real Meta endpoint and raises on 4xx.
    with pytest.raises(HTTPStatusError):
        await client.post(
            f"/api/v1/instagram/oauth/callback?code=test_auth_code&state={org.id}",
            headers={"Authorization": f"Bearer {user.access_token}"},
        )


@pytest.mark.asyncio
async def test_list_instagram_accounts(client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession):
    """Test listing organization's Instagram accounts"""
    user, org = user_with_org

    # Create test Instagram account
    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_acct_list",
            organization_id=org.id,
            ig_user_id="123456789",
            username="test_instagram_user",
            access_token_encrypted=vault.encrypt("test_token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        await session.commit()

    response = await client.get(
        f"/api/v1/instagram/accounts?organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["username"] == "test_instagram_user"
    assert data[0]["ig_user_id"] == "123456789"
    assert "access_token_encrypted" not in data[0]  # Should not expose encrypted token


@pytest.mark.asyncio
async def test_get_instagram_account_detail(client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession):
    """Test getting specific Instagram account details"""
    user, org = user_with_org

    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_acct_detail",
            organization_id=org.id,
            ig_user_id="987654321",
            username="detail_test_user",
            access_token_encrypted=vault.encrypt("test_token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        await session.commit()
        account_id = ig_account.id

    response = await client.get(
        f"/api/v1/instagram/accounts/{account_id}?organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ig_user_id"] == "987654321"
    assert data["username"] == "detail_test_user"


@pytest.mark.asyncio
async def test_disconnect_instagram_account(client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession):
    """Test disconnecting/deleting an Instagram account"""
    user, org = user_with_org

    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_acct_disconnect",
            organization_id=org.id,
            ig_user_id="555555555",
            username="disconnect_test_user",
            access_token_encrypted=vault.encrypt("test_token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        await session.commit()
        account_id = ig_account.id

    response = await client.delete(
        f"/api/v1/instagram/accounts/{account_id}?organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_schedule_post_success(client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession):
    """Test successfully scheduling a post"""
    user, org = user_with_org

    # Create Instagram account first
    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_acct_schedule_success",
            organization_id=org.id,
            ig_user_id="611111111",
            username="post_test_user",
            access_token_encrypted=vault.encrypt("test_token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        await session.commit()
        account_id = ig_account.id

    publish_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    response = await client.post(
        f"/api/v1/posts/schedule?account_id={account_id}&organization_id={org.id}",
        json={
            "caption": "Test Instagram post #testing",
            "media_urls": "https://example.com/image1.jpg,https://example.com/image2.jpg",
            "publish_at": publish_at,
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["caption"] == "Test Instagram post #testing"
    assert data["status"] == ScheduledPostStatus.SCHEDULED
    assert "media_urls" in data


@pytest.mark.asyncio
async def test_schedule_post_with_inactive_account(
    client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession
):
    """Test scheduling post fails if Instagram account is inactive"""
    user, org = user_with_org

    # Create inactive Instagram account
    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_acct_inactive",
            organization_id=org.id,
            ig_user_id="111111111",
            username="inactive_user",
            access_token_encrypted=vault.encrypt("test_token"),
            is_active=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        await session.commit()
        account_id = ig_account.id

    publish_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    response = await client.post(
        f"/api/v1/posts/schedule?account_id={account_id}&organization_id={org.id}",
        json={
            "caption": "Test post on inactive account",
            "media_urls": "https://example.com/image.jpg",
            "publish_at": publish_at,
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_scheduled_posts(client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession):
    """Test listing scheduled posts with optional status filtering"""
    user, org = user_with_org

    # Create Instagram account and scheduled post
    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_acct_scheduled",
            organization_id=org.id,
            ig_user_id="777777777",
            username="list_test_user",
            access_token_encrypted=vault.encrypt("test_token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        await session.flush()

        scheduled_post = ScheduledPost(
            id="test_post_id",
            instagram_account_id=ig_account.id,
            caption="Test post for listing",
            media_urls="https://example.com/image.jpg",
            publish_at=datetime.now(UTC) + timedelta(hours=2),
            status=ScheduledPostStatus.SCHEDULED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(scheduled_post)
        await session.commit()

    response = await client.get(
        f"/api/v1/posts/scheduled?account_id={ig_account.id}&organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["caption"] == "Test post for listing"
    assert data[0]["status"] == ScheduledPostStatus.SCHEDULED


@pytest.mark.asyncio
async def test_list_scheduled_posts_with_status_filter(
    client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession
):
    """Test filtering scheduled posts by status"""
    user, org = user_with_org

    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_acct_filtered",
            organization_id=org.id,
            ig_user_id="888888888",
            username="filter_test_user",
            access_token_encrypted=vault.encrypt("test_token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        await session.flush()

        # Create posts with different statuses
        post_draft = ScheduledPost(
            id="draft_post_id",
            instagram_account_id=ig_account.id,
            caption="Draft post",
            media_urls="https://example.com/image.jpg",
            publish_at=datetime.now(UTC) + timedelta(hours=3),
            status=ScheduledPostStatus.DRAFT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        post_scheduled = ScheduledPost(
            id="scheduled_post_id",
            instagram_account_id=ig_account.id,
            caption="Scheduled post",
            media_urls="https://example.com/image.jpg",
            publish_at=datetime.now(UTC) + timedelta(hours=2),
            status=ScheduledPostStatus.SCHEDULED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(post_draft)
        session.add(post_scheduled)
        await session.commit()

    response = await client.get(
        f"/api/v1/posts/scheduled?account_id={ig_account.id}&organization_id={org.id}&status_filter={ScheduledPostStatus.DRAFT}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert all(post["status"] == ScheduledPostStatus.DRAFT for post in data)


@pytest.mark.asyncio
async def test_get_scheduled_post_detail(client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession):
    """Test getting scheduled post details"""
    user, org = user_with_org

    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_acct_get_detail",
            organization_id=org.id,
            ig_user_id="999999999",
            username="detail_post_user",
            access_token_encrypted=vault.encrypt("test_token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        await session.flush()

        scheduled_post = ScheduledPost(
            id="detail_post_id",
            instagram_account_id=ig_account.id,
            caption="Detail post caption",
            media_urls="https://example.com/image1.jpg,https://example.com/image2.jpg",
            publish_at=datetime.now(UTC) + timedelta(hours=4),
            status=ScheduledPostStatus.SCHEDULED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(scheduled_post)
        await session.commit()
        post_id = scheduled_post.id

    response = await client.get(
        f"/api/v1/posts/{post_id}?account_id={ig_account.id}&organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["caption"] == "Detail post caption"
    assert data["status"] == ScheduledPostStatus.SCHEDULED


@pytest.mark.asyncio
async def test_update_scheduled_post_draft(client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession):
    """Test updating a draft post is allowed"""
    user, org = user_with_org

    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_acct_update_draft",
            organization_id=org.id,
            ig_user_id="121212121",
            username="update_draft_user",
            access_token_encrypted=vault.encrypt("test_token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        await session.flush()

        scheduled_post = ScheduledPost(
            id="update_post_id",
            instagram_account_id=ig_account.id,
            caption="Original caption",
            media_urls="https://example.com/image.jpg",
            publish_at=datetime.now(UTC) + timedelta(hours=5),
            status=ScheduledPostStatus.DRAFT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(scheduled_post)
        await session.commit()
        post_id = scheduled_post.id

    response = await client.patch(
        f"/api/v1/posts/{post_id}?account_id={ig_account.id}&organization_id={org.id}",
        json={
            "caption": "Updated caption",
            "media_urls": "https://example.com/updated.jpg",
            "publish_at": (datetime.now(UTC) + timedelta(hours=6)).isoformat(),
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["caption"] == "Updated caption"


@pytest.mark.asyncio
async def test_update_published_post_fails(client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession):
    """Test updating a published post returns error"""
    user, org = user_with_org

    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_acct_update_fail",
            organization_id=org.id,
            ig_user_id="202020202",
            username="published_user",
            access_token_encrypted=vault.encrypt("test_token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        await session.flush()

        scheduled_post = ScheduledPost(
            id="published_post_id",
            instagram_account_id=ig_account.id,
            caption="Published post",
            media_urls="https://example.com/image.jpg",
            publish_at=datetime.now(UTC) - timedelta(hours=1),
            status=ScheduledPostStatus.PUBLISHED,
            instagram_post_id="ig_post_123",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(scheduled_post)
        await session.commit()
        post_id = scheduled_post.id

    response = await client.patch(
        f"/api/v1/posts/{post_id}?account_id={ig_account.id}&organization_id={org.id}",
        json={
            "caption": "Try to update published post",
            "media_urls": "https://example.com/image.jpg",
            "publish_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_scheduled_post_allowed(client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession):
    """Test deleting a scheduled post is allowed"""
    user, org = user_with_org

    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_acct_delete_ok",
            organization_id=org.id,
            ig_user_id="303030303",
            username="delete_user",
            access_token_encrypted=vault.encrypt("test_token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        await session.flush()

        scheduled_post = ScheduledPost(
            id="delete_post_id",
            instagram_account_id=ig_account.id,
            caption="Post to delete",
            media_urls="https://example.com/image.jpg",
            publish_at=datetime.now(UTC) + timedelta(hours=7),
            status=ScheduledPostStatus.SCHEDULED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(scheduled_post)
        await session.commit()
        post_id = scheduled_post.id

    response = await client.delete(
        f"/api/v1/posts/{post_id}?account_id={ig_account.id}&organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_published_post_fails(client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession):
    """Test deleting a published post returns error"""
    user, org = user_with_org

    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_acct_delete_fail",
            organization_id=org.id,
            ig_user_id="404040404",
            username="cannot_delete_user",
            access_token_encrypted=vault.encrypt("test_token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        await session.flush()

        scheduled_post = ScheduledPost(
            id="cannot_delete_post_id",
            instagram_account_id=ig_account.id,
            caption="Cannot delete this",
            media_urls="https://example.com/image.jpg",
            publish_at=datetime.now(UTC) - timedelta(hours=2),
            status=ScheduledPostStatus.PUBLISHED,
            instagram_post_id="ig_post_456",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(scheduled_post)
        await session.commit()
        post_id = scheduled_post.id

    response = await client.delete(
        f"/api/v1/posts/{post_id}?account_id={ig_account.id}&organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_access_control_manager_can_schedule_posts(
    client: AsyncClient, user_with_org: tuple[User, Organization], db_session: AsyncSession
):
    """Test manager role can schedule posts"""
    user, org = user_with_org
    # user is already owner from fixture, test passes assuming owner can schedule

    publish_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_acct_access_ctrl",
            organization_id=org.id,
            ig_user_id="505050505",
            username="manager_test_user",
            access_token_encrypted=vault.encrypt("test_token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        await session.commit()
        account_id = ig_account.id

    response = await client.post(
        f"/api/v1/posts/schedule?account_id={account_id}&organization_id={org.id}",
        json={
            "caption": "Manager scheduled post",
            "media_urls": "https://example.com/image.jpg",
            "publish_at": publish_at,
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 201



