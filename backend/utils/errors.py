"""
AutoDL Flow - 统一错误处理模块
"""
import logging
import traceback
from flask import jsonify, request
from functools import wraps

logger = logging.getLogger(__name__)


class APIError(Exception):
    """API 错误异常类"""
    def __init__(self, message, status_code=500, error_code=None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)


class ValidationError(APIError):
    """验证错误（400）"""
    def __init__(self, message, error_code='VALIDATION_ERROR'):
        super().__init__(message, status_code=400, error_code=error_code)


class NotFoundError(APIError):
    """资源未找到错误（404）"""
    def __init__(self, message='Resource not found', error_code='NOT_FOUND'):
        super().__init__(message, status_code=404, error_code=error_code)


class UnauthorizedError(APIError):
    """未授权错误（403）"""
    def __init__(self, message='Unauthorized', error_code='UNAUTHORIZED'):
        super().__init__(message, status_code=403, error_code=error_code)


def handle_api_error(error):
    """处理 APIError 异常"""
    response = jsonify({
        'error': error.message,
        'error_code': error.error_code
    })
    response.status_code = error.status_code
    
    # 记录错误日志
    logger.error(
        f"API Error [{error.status_code}]: {error.message} (code: {error.error_code})",
        extra={
            'error_code': error.error_code,
            'status_code': error.status_code,
            'path': request.path if request else None,
            'method': request.method if request else None
        }
    )
    
    return response


def handle_generic_error(error):
    """处理通用异常"""
    from werkzeug.exceptions import NotFound
    
    # 如果是 404 错误，记录详细的请求信息
    if isinstance(error, NotFound):
        logger.warning(
            f"404 Not Found: {request.path if request else 'unknown'}",
            exc_info=True,
            extra={
                'path': request.path if request else None,
                'method': request.method if request else None,
                'url': request.url if request else None,
                'query_string': request.query_string.decode('utf-8') if request and request.query_string else '',
                'remote_addr': request.remote_addr if request else None
            }
        )
    else:
        logger.error(
            f"Unhandled exception: {str(error)}",
            exc_info=True,
            extra={
                'path': request.path if request else None,
                'method': request.method if request else None,
                'url': request.url if request else None
            }
        )
    
    # 对于 404 错误，返回 404 状态码
    if isinstance(error, NotFound):
        response = jsonify({
            'error': 'Not Found',
            'error_code': 'NOT_FOUND',
            'path': request.path if request else None
        })
        response.status_code = 404
        return response
    
    response = jsonify({
        'error': 'Internal server error',
        'error_code': 'INTERNAL_ERROR'
    })
    response.status_code = 500
    return response


def api_error_handler(f):
    """API 路由错误处理装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except APIError as e:
            return handle_api_error(e)
        except Exception as e:
            logger.error(
                f"Unhandled exception in {f.__name__}: {str(e)}",
                exc_info=True,
                extra={
                    'function': f.__name__,
                    'path': request.path if request else None,
                    'method': request.method if request else None
                }
            )
            return handle_generic_error(e)
    return decorated_function


def log_error(message, exception=None, level='error', **kwargs):
    """
    统一的错误日志记录函数
    
    Args:
        message: 错误消息
        exception: 异常对象（可选）
        level: 日志级别 ('debug', 'info', 'warning', 'error', 'critical')
        **kwargs: 额外的上下文信息
    """
    log_func = getattr(logger, level.lower(), logger.error)
    
    if exception:
        log_func(
            message,
            exc_info=True,
            extra=kwargs
        )
    else:
        log_func(
            message,
            extra=kwargs
        )

