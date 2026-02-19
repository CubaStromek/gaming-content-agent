"""WordPress Publishing API: /api/wp/*."""

import requests as http_requests
from flask import Blueprint, request
from werkzeug.utils import secure_filename

from web.auth import require_auth
from web.helpers import json_response
import wp_publisher
import publish_log
import config

wp_api_bp = Blueprint('wp_api', __name__)

ALLOWED_MEDIA_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


@wp_api_bp.route('/api/wp/status')
def api_wp_status():
    return json_response({
        'configured': wp_publisher.is_configured(),
        'url': config.WP_URL if wp_publisher.is_configured() else '',
    })


@wp_api_bp.route('/api/wp/categories')
def api_wp_categories():
    if not wp_publisher.is_configured():
        return json_response({'error': 'WordPress not configured'}), 400

    force_refresh = request.args.get('refresh') == '1'
    lang = request.args.get('lang')
    categories, error = wp_publisher.get_categories(force_refresh=force_refresh, lang=lang)
    if error:
        return json_response({'error': error}), 500

    return json_response({'categories': categories})


@wp_api_bp.route('/api/wp/status-tags')
def api_wp_status_tags():
    if not wp_publisher.is_configured():
        return json_response({'error': 'WordPress not configured'}), 400

    force_refresh = request.args.get('refresh') == '1'
    tags, error = wp_publisher.get_status_tags(force_refresh=force_refresh)
    if error:
        return json_response({'error': error}), 500

    return json_response({'status_tags': tags})


@wp_api_bp.route('/api/wp/upload-from-url', methods=['POST'])
@require_auth
def api_wp_upload_from_url():
    if not wp_publisher.is_configured():
        return json_response({'error': 'WordPress not configured'}), 400

    data = request.get_json()
    image_url = (data.get('url') or '').strip()
    caption = (data.get('caption') or '').strip()
    alt_text = (data.get('alt_text') or '').strip()

    if not image_url:
        return json_response({'error': 'Missing URL'}), 400

    img_resp = http_requests.get(image_url, timeout=15)
    if img_resp.status_code != 200:
        return json_response({'error': f'Cannot download image: HTTP {img_resp.status_code}'}), 502

    content_type = img_resp.headers.get('Content-Type', 'image/jpeg')
    filename = image_url.split('/')[-1].split('?')[0] or 'rawg-image.jpg'
    if '.' not in filename:
        filename = 'rawg-image.jpg'

    media_id, error = wp_publisher.upload_media_file(
        file_data=img_resp.content,
        filename=secure_filename(filename),
        content_type=content_type,
        caption=caption,
        alt_text=alt_text,
    )

    if error:
        return json_response({'error': error}), 500

    return json_response({'media_id': media_id})


@wp_api_bp.route('/api/wp/upload-media', methods=['POST'])
@require_auth
def api_wp_upload_media():
    if not wp_publisher.is_configured():
        return json_response({'error': 'WordPress not configured'}), 400

    if 'file' not in request.files:
        return json_response({'error': 'No file provided'}), 400

    f = request.files['file']
    if not f.filename:
        return json_response({'error': 'Empty filename'}), 400

    content_type = f.content_type or 'application/octet-stream'
    if content_type not in ALLOWED_MEDIA_TYPES:
        return json_response({'error': f'Unsupported file type: {content_type}. Allowed: {", ".join(ALLOWED_MEDIA_TYPES)}'}), 400

    safe_filename = secure_filename(f.filename)
    if not safe_filename:
        return json_response({'error': 'Invalid filename'}), 400

    file_data = f.read()
    if len(file_data) > MAX_UPLOAD_SIZE:
        return json_response({'error': f'File too large. Maximum: {MAX_UPLOAD_SIZE // (1024*1024)} MB'}), 400

    caption = request.form.get('caption', '').strip()
    alt_text = request.form.get('alt_text', '').strip()

    media_id, error = wp_publisher.upload_media_file(
        file_data=file_data,
        filename=safe_filename,
        content_type=content_type,
        caption=caption,
        alt_text=alt_text,
    )

    if error:
        return json_response({'error': error}), 500

    return json_response({'media_id': media_id})


@wp_api_bp.route('/api/wp/publish', methods=['POST'])
@require_auth
def api_wp_publish():
    if not wp_publisher.is_configured():
        return json_response({'error': 'WordPress not configured'}), 400

    try:
        data = request.get_json(force=True)
    except Exception:
        return json_response({'error': 'Invalid JSON'}), 400
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    categories = data.get('categories', [])
    tags_str = data.get('tags', '')
    status_tag = data.get('status_tag', '').strip()
    lang = data.get('lang', '')
    featured_media_id = data.get('featured_media_id')

    if not title or not content:
        return json_response({'error': 'Title and content are required'}), 400

    tag_names = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []

    content = wp_publisher.strip_first_heading(content)

    score = data.get('score', 3)
    source_info = data.get('source_info', '').strip()
    topic_meta = data.get('topic_meta') or {}

    result, error = wp_publisher.create_draft(
        title=title,
        content=content,
        category_ids=categories if categories else None,
        tag_names=tag_names if tag_names else None,
        lang=lang if lang else None,
        featured_image_id=featured_media_id,
        status_tag=status_tag if status_tag else None,
        source_info=source_info if source_info else None,
    )

    if error:
        return json_response({'error': error}), 500

    try:
        log_entry = {
            'action': 'published',
            'score': score,
            'run_id': topic_meta.get('run_id', ''),
            'topic_index': topic_meta.get('topic_index', 0),
            'topic': topic_meta.get('topic', ''),
            'suggested_title': topic_meta.get('suggested_title', ''),
            'published_title': title,
            'virality_score': topic_meta.get('virality_score', 0),
            'seo_keywords': topic_meta.get('seo_keywords', ''),
            'sources': topic_meta.get('sources', []),
            'source_count': topic_meta.get('source_count', 0),
            'categories_cs': categories if lang == 'cs' else [],
            'categories_en': categories if lang == 'en' else [],
            'status_tag': status_tag,
            'tags': tags_str,
            'lang': lang,
            'has_image': featured_media_id is not None,
            'wp_post_cs': result.get('id') if lang == 'cs' else None,
            'wp_post_en': result.get('id') if lang == 'en' else None,
        }
        publish_log.log_decision(log_entry)
    except Exception:
        pass

    return json_response({'post': result})


@wp_api_bp.route('/api/wp/publish-both', methods=['POST'])
@require_auth
def api_wp_publish_both():
    if not wp_publisher.is_configured():
        return json_response({'error': 'WordPress not configured'}), 400

    try:
        data = request.get_json(force=True)
    except Exception:
        return json_response({'error': 'Invalid JSON'}), 400
    title_cs = data.get('title_cs', '').strip()
    title_en = data.get('title_en', '').strip()
    content_cs = data.get('content_cs', '').strip()
    content_en = data.get('content_en', '').strip()
    categories_cs = data.get('categories_cs', data.get('categories', []))
    categories_en = data.get('categories_en', data.get('categories', []))
    tags_str = data.get('tags', '')
    status_tag_cs = data.get('status_tag_cs', data.get('status_tag', '')).strip()
    status_tag_en = data.get('status_tag_en', data.get('status_tag', '')).strip()
    featured_media_id = data.get('featured_media_id')
    score = data.get('score', 3)
    source_info = data.get('source_info', '').strip()
    topic_meta = data.get('topic_meta') or {}

    if not title_cs or not content_cs or not title_en or not content_en:
        return json_response({'error': 'Both CS and EN title+content are required'}), 400

    tag_names = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []

    content_cs = wp_publisher.strip_first_heading(content_cs)
    content_en = wp_publisher.strip_first_heading(content_en)

    result_cs, error_cs = wp_publisher.create_draft(
        title=title_cs,
        content=content_cs,
        category_ids=categories_cs if categories_cs else None,
        tag_names=tag_names if tag_names else None,
        lang='cs',
        featured_image_id=featured_media_id,
        status_tag=status_tag_cs if status_tag_cs else None,
        source_info=source_info if source_info else None,
    )
    if error_cs:
        return json_response({'error': f'CS draft failed: {error_cs}'}), 500

    result_en, error_en = wp_publisher.create_draft(
        title=title_en,
        content=content_en,
        category_ids=categories_en if categories_en else None,
        tag_names=tag_names if tag_names else None,
        lang='en',
        featured_image_id=featured_media_id,
        status_tag=status_tag_en if status_tag_en else None,
        source_info=source_info if source_info else None,
    )
    if error_en:
        return json_response({'error': f'EN draft failed: {error_en}. CS draft was created: {result_cs["edit_url"]}'}), 500

    link_result, link_error = wp_publisher.link_translations(result_cs['id'], result_en['id'])

    try:
        log_entry = {
            'action': 'published',
            'score': score,
            'run_id': topic_meta.get('run_id', ''),
            'topic_index': topic_meta.get('topic_index', 0),
            'topic': topic_meta.get('topic', ''),
            'suggested_title': topic_meta.get('suggested_title', ''),
            'published_title': title_cs,
            'virality_score': topic_meta.get('virality_score', 0),
            'seo_keywords': topic_meta.get('seo_keywords', ''),
            'sources': topic_meta.get('sources', []),
            'source_count': topic_meta.get('source_count', 0),
            'categories_cs': categories_cs if categories_cs else [],
            'categories_en': categories_en if categories_en else [],
            'status_tag_cs': status_tag_cs,
            'status_tag_en': status_tag_en,
            'tags': tags_str,
            'lang': 'both',
            'has_image': featured_media_id is not None,
            'wp_post_cs': result_cs.get('id'),
            'wp_post_en': result_en.get('id'),
        }
        publish_log.log_decision(log_entry)
    except Exception:
        pass

    return json_response({
        'post_cs': result_cs,
        'post_en': result_en,
        'linked': link_result is not None,
        'link_error': link_error,
    })


@wp_api_bp.route('/api/wp/log-skip', methods=['POST'])
@require_auth
def api_wp_log_skip():
    try:
        data = request.get_json(force=True)
    except Exception:
        return json_response({'error': 'Invalid JSON'}), 400
    topic_meta = data.get('topic_meta') or {}

    try:
        log_entry = {
            'action': 'skipped',
            'score': 0,
            'run_id': topic_meta.get('run_id', ''),
            'topic_index': topic_meta.get('topic_index', 0),
            'topic': topic_meta.get('topic', ''),
            'suggested_title': topic_meta.get('suggested_title', ''),
            'virality_score': topic_meta.get('virality_score', 0),
            'seo_keywords': topic_meta.get('seo_keywords', ''),
            'sources': topic_meta.get('sources', []),
            'source_count': topic_meta.get('source_count', 0),
        }
        publish_log.log_decision(log_entry)
    except Exception as e:
        return json_response({'error': str(e)}), 500

    return json_response({'ok': True})


@wp_api_bp.route('/api/wp/publish-stats')
def api_wp_publish_stats():
    try:
        stats = publish_log.get_stats()
        return json_response(stats)
    except Exception as e:
        return json_response({'error': str(e)}), 500
