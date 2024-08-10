import redis
from rq import Queue
from pushjob import example_job 



redis_conn = redis.Redis(host='localhost', port=6379, db=0)

queue_name = 'api_req_queue'
queue = Queue(queue_name, connection=redis_conn)

# Enqueue jobs
for i in range(1):
    job = queue.enqueue(example_job, i, i + 1)
    print(f"Enqueued job {job.id} with args ({i}, {i + 1})")
    
