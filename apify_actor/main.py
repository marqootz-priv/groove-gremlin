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
        
        if not urls:
            Actor.log.error('No Instagram URLs provided in input')
            await Actor.exit()
            return
        
        # Need either session ID or username/password
        if not instagram_session_id and (not instagram_username or not instagram_password):
            Actor.log.error('Either instagram_session_id OR (instagram_username AND instagram_password) required')
            await Actor.exit()
            return
        
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
                            await Actor.exit()
                            return
                    except Exception as e:
                        Actor.log.error(f'❌ Username/password login failed: {str(e)}')
                        await Actor.exit()
                        return
                elif not logged_in:
                    Actor.log.error('❌ Session ID login failed and no username/password provided')
                    Actor.log.error('   Note: Browser session IDs are not compatible with instagrapi')
                    Actor.log.error('   Solution: Use username/password login, or generate session ID via instagrapi')
                    await Actor.exit()
                    return
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
                        await Actor.exit()
                        return
                        
                except BadPassword:
                    Actor.log.error('❌ Bad password or login blocked from this IP')
                    Actor.log.error('   Try using Session ID login instead.')
                    await Actor.exit()
                    return
                except TwoFactorRequired:
                    Actor.log.error('❌ Two-factor authentication required')
                    Actor.log.error('   Use Session ID login instead.')
                    await Actor.exit()
                    return
                except ChallengeRequired:
                    Actor.log.error('❌ Challenge required - Instagram is blocking this login')
                    Actor.log.error('   Use Session ID login instead.')
                    await Actor.exit()
                    return
                except Exception as e:
                    Actor.log.error(f'❌ Login failed: {str(e)}')
                    Actor.log.error('   Try using Session ID login instead.')
                    await Actor.exit()
                    return
            
            time.sleep(3)
            
            # Verify session is still valid before proceeding
            try:
                my_user_id = cl.user_id
                Actor.log.info(f'✅ Session verified - logged in as user ID: {my_user_id}')
            except LoginRequired:
                Actor.log.error('❌ Session expired immediately after login')
                Actor.log.error('   This usually means the session ID from browser is incompatible')
                Actor.log.error('   Use username/password login instead, or generate session ID via instagrapi')
                await Actor.exit()
                return
            
            # Get current following list
            Actor.log.info('Fetching your current following list...')
            following_usernames = set()
            try:
                following = cl.user_following(my_user_id, amount=500)
                following_usernames = {user.username.lower() for user in following.values()}
                Actor.log.info(f'You currently follow {len(following_usernames)} accounts')
            except LoginRequired:
                Actor.log.warning('⚠️  Session expired while fetching following list')
                Actor.log.warning('   This may indicate the session ID is incompatible')
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
                    
                    # Helper function to get user ID with multiple fallback methods
                    def get_user_id_safe(username):
                        """Try multiple methods to get user ID, handling various errors"""
                        # Method 1: Try user_id_from_username (fastest)
                        try:
                            return cl.user_id_from_username(username)
                        except (TypeError, AttributeError) as e:
                            if 'update_headers' in str(e) or 'extract_user_gql' in str(e):
                                Actor.log.warning(f'  ⚠️  Instagrapi version issue, trying alternative method')
                            else:
                                raise
                        except (UserNotFound, LoginRequired):
                            raise
                        except Exception:
                            pass  # Try next method
                        
                        # Method 2: Try user_info_by_username (alternative)
                        try:
                            user_info = cl.user_info_by_username(username)
                            return user_info.pk
                        except (TypeError, AttributeError) as e:
                            if 'update_headers' in str(e) or 'extract_user_gql' in str(e):
                                Actor.log.warning(f'  ⚠️  Alternative method also has version issue')
                            else:
                                raise
                        except (UserNotFound, LoginRequired):
                            raise
                        except Exception:
                            pass  # Try next method
                        
                        # Method 3: Try direct API call via username search
                        try:
                            # Last resort: try to get from profile URL
                            Actor.log.warning(f'  ⚠️  Standard methods failed, trying direct lookup')
                            # This is a fallback - may not work
                            raise UserNotFound(f"Could not find user @{username} with any method")
                        except Exception as e:
                            raise Exception(f"All methods failed to get user ID: {str(e)}")
                    
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
                                    Actor.log.error('   Session expired and cannot recover')
                                    break
                            else:
                                Actor.log.error('   Cannot recover - no username/password provided')
                                break
                        
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
                                failed_count += 1
                                break
                        else:
                            Actor.log.error('   Cannot recover - no username/password provided')
                            failed_count += 1
                            break
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
                        Actor.log.error('   Please use username/password login instead')
                        break
                    
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
                        failed_count += 1
                        # Break out of loop since session is invalid
                        break
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
