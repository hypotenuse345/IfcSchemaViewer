def timer_wrapper(func):
    def func_wrapper(*args, **kwargs):
        from time import time
        import logging
        time_start = time()
        result = func(*args, **kwargs)
        time_end = time()
        time_spend = time_end - time_start
        # func = function()
        logging.info('%s.%s cost time: %.3f ms' % (func.__module__, func.__qualname__, time_spend*1000))
        return result
    return func_wrapper