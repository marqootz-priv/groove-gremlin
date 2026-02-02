"""
Apify Actor for Instagram Following
Uses Instagrapi with Session ID login (more reliable than username/password).
"""

from apify import Actor
from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired, 
    ChallengeRequired, 
    TwoFactorRequired,
    PleaseWaitFewMinutes,
    UserNotFound,
    ClientError,
    BadPassword,
    ReloginAttemptExceeded
)
import time
import random
import json
import asyncio


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}
        
        Actor.log.info(f'Received input: {json.dumps(actor_input, indent=2)}')
        
        if 'input' in actor_input and isinstance(actor_input['input'], dict):
            Actor.log.info('Input was wrapped in "input" key, unwrapping...')
            actor_input = actor_input['input']
        
        urls = actor_input.get('urls', [])
        
        if isinstance(urls, str):
            urls = [url.strip() for url in urls.split('\n') if url.strip()]
        
        # Configuration - support both session ID and username/password
        instagram_session_id = actor_input.get('instagram_session_id')
        instagram_username = actor_input.get('instagram_username')
        instagram_password = actor_input.get('instagram_password')
        delay_min = actor_input.get('delay_min', 30)
        delay_max = actor_input.get('delay_max', 90)
        max_follows = actor_input.get('max_follows', 20)
        skip_following_check = actor_input.get('skip_following_check', True)
        
        if not urls:
            Actor.log.error('No Instagram URLs provided in input')
            raise RuntimeError('No Instagram URLs provided in input')

        # Need either session ID or username/password
        if not instagram_session_id and (not instagram_username or not instagram_password):
            Actor.log.error('Either instagram_session_id OR (instagram_username AND instagram_password) required')
            raise RuntimeError('Instagram credentials required')
        
        # Extract usernames from URLs
        usernames_to_follow = []
        for url in urls[:max_follows]:
            username = url.replace('https://www.instagram.com/', '').replace('http://www.instagram.com/', '').rstrip('/')
            if username and '/' not in username:
                usernames_to_follow.append(username)
        
        Actor.log.info(f'Will attempt to follow {len(usernames_to_follow)} accounts')
        Actor.log.info(f'Rate limit: {delay_min}-{delay_max} seconds between follows')
        
        # Initialize Instagram client
        cl = Client()
        
        # Configure client settings
        cl.set_settings({
            "uuids": {
                "phone_id": "57d64c41-a916-3fa5-bd7a-3796c1dab122",
                "uuid": "8aa373c6-f316-44d7-b49e-d74563f4a8f3",
                "client_session_id": "6c296d0a-3534-4dce-b5aa-a6a6ab017443",
                "advertising_id": "8dc88b76-dfbc-44dc-abbc-31a6f1d54b04",
                "device_id": "android-e021b636049dc0e9"
            },
            "device_settings": {
                "app_version": "269.0.0.18.75",
                "android_version": 26,
                "android_release": "8.0.0",
                "dpi": "480dpi",
                "resolution": "1080x1920",
                "manufacturer": "OnePlus",
                "device": "OnePlus6T",
                "model": "ONEPLUS A6013",
                "cpu": "qcom",
                "version_code": "314665256"
            },
            "user_agent": "Instagram 269.0.0.18.75 Android (26/8.0.0; 480dpi; 1080x1920; OnePlus; ONEPLUS A6013; OnePlus6T; qcom; en_US; 314665256)"
        })
        
        cl.delay_range = [1, 3]
        
        try:
            # Try session ID login first (most reliable)
            if instagram_session_id:
                Actor.log.info('Logging into Instagram via Session ID...')
                Actor.log.info(f'Session ID length: {len(instagram_session_id)} chars')
                
                try:
                    logged_in = cl.login_by_sessionid(instagram_session_id)
                    
                    if logged_in:
                        Actor.log.info('✅ Successfully logged in via Session ID')
                        
                        # Verify session is actually valid by trying a simple operation
                        try:
                            test_user_id = cl.user_id
                            Actor.log.info(f'✅ Session validated - logged in as user ID: {test_user_id}')
                        except LoginRequired:
                            Actor.log.warning('⚠️  Session ID from browser may not be compatible with mobile API')
                            Actor.log.warning('   Instagram invalidated the session - falling back to username/password')
                            logged_in = False
                        except Exception as e:
                            Actor.log.warning(f'⚠️  Session validation failed: {str(e)}')
                            logged_in = False
                    else:
                        Actor.log.warning('⚠️  Session ID login returned False - session may be expired')
                        logged_in = False
                        
                except LoginRequired:
                    Actor.log.warning('⚠️  Session ID from browser not compatible with mobile API')
                    Actor.log.warning('   Instagram requires mobile session ID - falling back to username/password')
                    logged_in = False
                except Exception as e:
                    Actor.log.warning(f'⚠️  Session ID login failed: {str(e)}')
                    Actor.log.warning('   Falling back to username/password login')
                    logged_in = False
                
                # If session ID login failed, try username/password as fallback
                if not logged_in and instagram_username and instagram_password:
                    Actor.log.info('Attempting username/password login as fallback...')
                    try:
                        logged_in = cl.login(instagram_username, instagram_password)
                        if logged_in:
                            Actor.log.info('✅ Successfully logged in via username/password')
                            # Save the new session ID for future use
                            new_session_id = cl.sessionid
                            Actor.log.info(f'💡 New session ID generated: {new_session_id[:20]}...')
                            Actor.log.info('   Save this session ID for future runs to avoid login issues')
                        else:
                            Actor.log.error('❌ Username/password login also failed')
                            raise RuntimeError('Instagram login failed - credentials invalid or expired')
                    except Exception as e:
                        Actor.log.error(f'❌ Username/password login failed: {str(e)}')
                        raise RuntimeError(f'Instagram login failed: {str(e)}')
                elif not logged_in:
                    Actor.log.error('❌ Session ID login failed and no username/password provided')
                    Actor.log.error('   Note: Browser session IDs are not compatible with instagrapi')
                    raise RuntimeError('Instagram login failed - use username/password or valid session ID')
            else:
                # Fall back to username/password
                Actor.log.info('Logging into Instagram via username/password...')
                Actor.log.info(f'Username: {instagram_username}')
                
                try:
                    logged_in = cl.login(instagram_username, instagram_password)
                    
                    if logged_in:
                        Actor.log.info('✅ Successfully logged in')
                    else:
                        Actor.log.error('❌ Login returned False')
                        raise RuntimeError('Instagram login failed')

                except BadPassword:
                    Actor.log.error('❌ Bad password or login blocked from this IP')
                    raise RuntimeError('Bad password or login blocked')
                except TwoFactorRequired:
                    Actor.log.error('❌ Two-factor authentication required')
                    raise RuntimeError('Two-factor auth required - use Session ID login instead')
                except ChallengeRequired:
                    Actor.log.error('❌ Challenge required - Instagram is blocking this login')
                    raise RuntimeError('Challenge required - use Session ID login instead')
                except Exception as e:
                    Actor.log.error(f'❌ Login failed: {str(e)}')
                    raise RuntimeError(f'Instagram login failed: {str(e)}')
            
            time.sleep(3)
            
            # Verify session is still valid before proceeding
            try:
                my_user_id = cl.user_id
                Actor.log.info(f'✅ Session verified - logged in as user ID: {my_user_id}')
            except LoginRequired:
                Actor.log.error('❌ Session expired immediately after login')
                Actor.log.error('   This usually means the session ID from browser is incompatible')
                raise RuntimeError('Session expired - refresh credentials or use username/password')
            
            # Get current following list (optional - often returns 400 for browser sessions)
            following_usernames = set()
            if skip_following_check:
                Actor.log.info('Skipping following list check (skip_following_check=True)')
            else:
                Actor.log.info('Fetching your current following list...')
                try:
                    following = cl.user_following(my_user_id, amount=500)
                    following_usernames = {user.username.lower() for user in following.values()}
                    Actor.log.info(f'You currently follow {len(following_usernames)} accounts')
                except LoginRequired:
                    Actor.log.warning('⚠️  Session expired while fetching following list')
                    Actor.log.warning('   Continuing anyway, but some operations may fail')
                except Exception as e:
                    Actor.log.warning(f'Could not fetch following list: {str(e)}')
            
            # Follow accounts
            followed_count = 0
            failed_count = 0
            already_following_count = 0
            
            for i, username in enumerate(usernames_to_follow, 1):
                try:
                    Actor.log.info(f'[{i}/{len(usernames_to_follow)}] Processing: @{username}')
                    
                    if username.lower() in following_usernames:
                        Actor.log.info(f'  ⏭️  Already following @{username}')
                        already_following_count += 1
                        await Actor.push_data({
                            'username': username,
                            'status': 'already_following',
                            'timestamp': time.time()
                        })
                        continue
                    
                    def _get_id_via_search(uname):
                        search_results = cl.search_users(uname, count=20)
                        for user in search_results:
                            if user.username.lower() == uname.lower():
                                return user.pk
                        raise UserNotFound(f"User @{uname} not found in search results")

                    def get_user_id_safe(username):
                        """Use private mobile API only - avoid public endpoints that return HTML instead of JSON"""
                        methods = [
                            ('user_info_by_username_v1', lambda: cl.user_info_by_username_v1(username).pk),
                            ('search_users', lambda: _get_id_via_search(username)),
                        ]
                        last_error = None
                        for method_name, fn in methods:
                            for attempt in range(2):
                                try:
                                    return fn()
                                except (UserNotFound, LoginRequired):
                                    raise
                                except Exception as e:
                                    last_error = e
                                    if attempt == 0:
                                        Actor.log.warning(f'  ⚠️  {method_name} failed (attempt 1/2): {str(e)[:80]}')
                                        time.sleep(2)
                                    else:
                                        Actor.log.warning(f'  ⚠️  {method_name} failed (attempt 2/2)')
                                        break
                        raise Exception(f"Could not get user ID for @{username}: {last_error}")
                    
                    try:
                        # Verify session before getting user ID
                        try:
                            _ = cl.user_id  # Quick session check
                        except LoginRequired:
                            Actor.log.error(f'  ❌ Session expired before processing @{username}')
                            if instagram_username and instagram_password:
                                Actor.log.info('  🔄 Attempting to re-login with username/password...')
                                try:
                                    cl.login(instagram_username, instagram_password)
                                    Actor.log.info('  ✅ Re-login successful')
                                except Exception as relogin_e:
                                    Actor.log.error(f'  ❌ Re-login failed: {str(relogin_e)}')
                                    raise RuntimeError('Session expired - re-login failed')
                            else:
                                Actor.log.error('   Cannot recover - no username/password provided')
                                raise RuntimeError('Session expired - no credentials to re-login')
                        
                        user_id = get_user_id_safe(username)
                        Actor.log.info(f'  Found user ID: {user_id}')
                    except UserNotFound:
                        Actor.log.warning(f'  ❌ User @{username} not found')
                        failed_count += 1
                        await Actor.push_data({
                            'username': username,
                            'status': 'user_not_found',
                            'timestamp': time.time()
                        })
                        continue
                    except LoginRequired:
                        Actor.log.error(f'  ❌ Login required - session expired')
                        if instagram_username and instagram_password:
                            Actor.log.info('  🔄 Attempting to re-login...')
                            try:
                                cl.login(instagram_username, instagram_password)
                                Actor.log.info('  ✅ Re-login successful, retrying...')
                                # Retry getting user ID after re-login
                                try:
                                    user_id = get_user_id_safe(username)
                                    Actor.log.info(f'  Found user ID after re-login: {user_id}')
                                except Exception as retry_e:
                                    Actor.log.error(f'  ❌ Still failed after re-login: {str(retry_e)}')
                                    failed_count += 1
                                    continue
                            except Exception as relogin_e:
                                Actor.log.error(f'  ❌ Re-login failed: {str(relogin_e)}')
                                raise RuntimeError('Session expired - re-login failed')
                        else:
                            Actor.log.error('   Cannot recover - no username/password provided')
                            raise RuntimeError('Session expired - no credentials to re-login')
                    except Exception as e:
                        Actor.log.warning(f'  ❌ Could not find @{username}: {str(e)}')
                        failed_count += 1
                        continue
                    
                    time.sleep(random.uniform(1, 2))
                    
                    # Verify session before each follow attempt
                    try:
                        # Quick session check
                        _ = cl.user_id
                    except LoginRequired:
                        Actor.log.error('❌ Session expired before following @{username}')
                        Actor.log.error('   The session ID from browser is not compatible with mobile API')
                        raise RuntimeError('Session expired - refresh credentials')
                    
                    try:
                        result = cl.user_follow(user_id)
                        if result:
                            Actor.log.info(f'  ✅ Followed @{username} successfully')
                            followed_count += 1
                            await Actor.push_data({
                                'username': username,
                                'status': 'followed',
                                'timestamp': time.time()
                            })
                        else:
                            Actor.log.warning(f'  ❌ Failed to follow @{username}')
                            failed_count += 1
                    except PleaseWaitFewMinutes:
                        Actor.log.warning(f'  ⏳ Rate limited! Waiting 5 minutes...')
                        time.sleep(300)
                        try:
                            result = cl.user_follow(user_id)
                            if result:
                                Actor.log.info(f'  ✅ Followed @{username} after waiting')
                                followed_count += 1
                            else:
                                failed_count += 1
                        except:
                            failed_count += 1
                    except LoginRequired:
                        Actor.log.error(f'  ❌ Login required - session expired while following @{username}')
                        Actor.log.error('   Please refresh your session ID and try again')
                        raise RuntimeError('Session expired during follow - refresh credentials')
                    except Exception as follow_error:
                        Actor.log.error(f'  ❌ Error following: {str(follow_error)}')
                        failed_count += 1
                    
                    if i < len(usernames_to_follow):
                        delay = random.uniform(delay_min, delay_max)
                        Actor.log.info(f'  ⏱️  Waiting {delay:.0f} seconds...')
                        time.sleep(delay)
                    
                    if i % 5 == 0 and i < len(usernames_to_follow):
                        extra_delay = random.uniform(120, 180)
                        Actor.log.info(f'  ☕ Taking a {extra_delay:.0f} second break...')
                        time.sleep(extra_delay)
                        
                except Exception as e:
                    Actor.log.error(f'  ❌ Unexpected error: {str(e)}')
                    failed_count += 1
                    time.sleep(10)
            
            # Summary
            Actor.log.info('=' * 60)
            Actor.log.info('Summary:')
            Actor.log.info(f'  ✅ Successfully followed: {followed_count}')
            Actor.log.info(f'  ⏭️  Already following: {already_following_count}')
            Actor.log.info(f'  ❌ Failed: {failed_count}')
            Actor.log.info('=' * 60)
            
            await Actor.set_value('output', {
                'followed': followed_count,
                'already_following': already_following_count,
                'failed': failed_count,
                'total_processed': len(usernames_to_follow)
            })
            
        except Exception as e:
            Actor.log.error(f'Fatal error: {str(e)}')
            import traceback
            Actor.log.error(traceback.format_exc())
            raise


if __name__ == '__main__':
    asyncio.run(main())
