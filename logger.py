import logging
import os
from datetime import datetime, timedelta
import sys
import time

class DailyLogger:
    def __init__(self, log_dir="log", max_days=10):
        self.log_dir = log_dir
        self.max_days = max_days
        self.logger = None
        self.current_date = None
        
        # 确保日志目录存在
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
        # 初始化日志
        self._setup_logger()
        
        # 清理旧日志
        self._cleanup_old_logs()
    
    def _setup_logger(self):
        """设置日志记录器"""
        # 使用本地时区
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 如果日期变化，重新设置日志
        if self.current_date != today:
            self.current_date = today
            
            # 创建新的日志记录器
            self.logger = logging.getLogger(f'daily_logger_{today}')
            self.logger.setLevel(logging.INFO)
            
            # 清除之前的处理器
            self.logger.handlers.clear()
            
            # 文件处理器
            log_file = os.path.join(self.log_dir, f'{today}.log')
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            
            # 控制台处理器
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            
            # 设置格式
            formatter = logging.Formatter('%(asctime)s - %(message)s', 
                                        datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            # 添加处理器
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def _cleanup_old_logs(self):
        """清理超过指定天数的旧日志文件"""
        try:
            # 使用本地时区
            cutoff_date = datetime.now() - timedelta(days=self.max_days)
            
            for filename in os.listdir(self.log_dir):
                if filename.endswith('.log'):
                    file_path = os.path.join(self.log_dir, filename)
                    
                    # 从文件名提取日期
                    try:
                        date_str = filename.replace('.log', '')
                        file_date = datetime.strptime(date_str, '%Y-%m-%d')
                        
                        if file_date < cutoff_date:
                            os.remove(file_path)
                            print(f"已删除旧日志文件: {filename}")
                    except ValueError:
                        # 文件名格式不正确，跳过
                        continue
        except Exception as e:
            print(f"清理旧日志时出错: {e}")
    
    def info(self, message):
        """记录信息级别日志"""
        self._setup_logger()  # 确保使用当前日期的日志
        self.logger.info(message)
        sys.stdout.flush()  # 强制刷新输出缓冲区
    
    def error(self, message):
        """记录错误级别日志"""
        self._setup_logger()  # 确保使用当前日期的日志
        self.logger.error(message)
        sys.stdout.flush()  # 强制刷新输出缓冲区
    
    def warning(self, message):
        """记录警告级别日志"""
        self._setup_logger()  # 确保使用当前日期的日志
        self.logger.warning(message)
        sys.stdout.flush()  # 强制刷新输出缓冲区

# 全局日志实例
_global_logger = None

def get_logger():
    """获取全局日志实例"""
    global _global_logger
    if _global_logger is None:
        _global_logger = DailyLogger()
    return _global_logger

def log_info(message):
    """记录信息日志的便捷函数"""
    get_logger().info(message)

def log_error(message):
    """记录错误日志的便捷函数"""
    get_logger().error(message)

def log_warning(message):
    """记录警告日志的便捷函数"""
    get_logger().warning(message)