# # monitor_script.py
# import redis
# from rq import Queue
# from rq.job import Job
# from rq.registry import FailedJobRegistry

# # Connect to Redis
# redis_conn = redis.Redis(host='localhost', port=6379)

# # Specify the queue name
# queue_name = 'default'
# q = Queue(name=queue_name, connection=redis_conn)

# # Fetch all jobs from the queue
# jobs = q.get_jobs()

# if not jobs:
#     print("No jobs found in the queue.")
# else:
#     for job in jobs:
#         try:
#             print(f"Job ID: {job.id}")
#             print(f"Job Status: {job.get_status()}")
#             print(f"Job Result: {job.result}")
#             print(f"Job Description: {job.description}")
#         except Exception as e:
#             print(f"Error fetching job {job.id}: {e}")

# # Access failed jobs for this queue
# failed_registry = FailedJobRegistry(queue=q)
# failed_jobs = failed_registry.get_job_ids()

# if not failed_jobs:
#     print("No failed jobs found in the queue.")
# else:
#     print("Failed Jobs:")
#     for job_id in failed_jobs:
#         try:
#             job = Job.fetch(job_id, connection=redis_conn)
#             print(f"Failed Job ID: {job.id}")
#             print(f"Failed Job Status: {job.get_status()}")
#             print(f"Failed Job Description: {job.description}")
#             print(f"Failed Job Result: {job.result}")
#         except Exception as e:
#             print(f"Error fetching failed job {job_id}: {e}")
