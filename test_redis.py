import redis





r = redis.Redis(host='localhost', port=6379, db=0)

# r.rpush("inprogress:task", "2: {'test2': 'active'}", "3: {'test3': 'active'}", "4: {'test4': 'active'}")
res17 = r.lpush(
                "inprogress_list", 
                "1: {'test1': 'active'}", 
                "2: {'test2': 'active'}",
                "3: {'test3': 'active'}",
                "4: {'test4': 'active'}"
                )

r.lrem("inprogress_list", 100, "1: {'test1': 'active'}")


remaining_bikes = r.lrange("inprogress_list", 0, -1)
# print(f"inprogress:task: {remaining_bikes}")
# r.lpush("inprogress_list","kkoiu")
# r.lpush("inprogress_list","kkolliu")
r.lpush("inprogress_list","kkwoiu")
# remaining_bikes = r.lrange("inprogress_list", 0, -1)

print(f"inprogress:task: {remaining_bikes}")

# r.lrem("inprogress_list",99,"kkoiu")
# remaining_bikes = r.lrange("inprogress_list", 0, -1)

# print(f"inprogress:task: {remaining_bikes}")




# res22 = r.rpush("bikes:repairs4", "bike:1", "bike:2", "bike:3")
# res22 = r.rpush("bikes:repairs", "bike:1", "bike:2", "bike:3")
# print(res22)  # >>> 3

# res23 = r.rpop("bikes:repairs")
# print(res23)  # >>> 'bike:3'

# res24 = r.lpop("bikes:repairs")
# print(res24)  # >>> 'bike:1'

# res25 = r.rpop("bikes:repairs")
# print(res25)  # >>> 'bike:2'

# res26 = r.rpop("bikes:repairs")
# print(res26)  # >>> None

# res27 = r.rpush("bikes:repairs", "bike:1", "bike:2", "bike:3", "bike:4", "bike:5")
# print(res27)  # >>> 5

# res28 = r.ltrim("bikes:repairs", -3, -1)
# print(res28)  # >>> True

# res29 = r.lrange("bikes:repairs", 0, -1)


# r = redis.Redis(host='localhost', port=6379, db=0)

# task_key = "task_12345"
# r.rpush(task_key, "testing")  

# r.delete(task_key)




# def get_rabbit_queues_status():
#     queueNames = [ glv.current_task_queue, glv.failed_tasks, glv.in_progress_tasks]
#     rqueue_tasks = {} 
#     for queue_name in queueNames:  
#         try:
#             queueuHandler = rabbit_server.queue_declare(queue=queue_name, durable=True)
#             queueLength = queueuHandler.method.message_count  

#             print(f"Queue '{queue_name}' has {queueLength} items.")
#             print("Members:")
#             if queue_name == "fixme":
#                 tasks = []
#                 for jobs in queueuHandler:
#                     task_data = jobs.decode('utf-8')
#                     task = json.loads(task_data)
#                     tasks.append(task)
#                 rqueue_tasks[queue_name] = {
#                     "queue_name": queue_name,
#                     "queue_length": queueLength,
#                     "jobs": tasks
#                 }
#             else:
#                 rqueue_tasks[queue_name] = {
#                         "queue_name": queue_name,
#                         "queue_length": queueLength,
#                         "jobs": []
#                     }
#         except redis.exceptions.RedisError as e:
#             print(f"An error occurred with queue '{queue_name}': {e}")
    
#     return rqueue_tasks

# def get_redis_jobs():
#     queue_names = [ glv.current_task_queue, glv.failed_tasks, glv.in_progress_tasks]
#     redis_tasks = {} 
#     for set_name in queue_names:
#         try: 
#             members = redis_conn.smembers(set_name)  
#             set_length = redis_conn.scard(set_name)
#             print(f"Set '{set_name}' has {set_length} members.")
#             print("Members:")
#             if set_name == glv.current_task_queue:
#                 tasks = []
#                 for jobs in members:
#                     task_data = jobs.decode('utf-8')
#                     task = json.loads(task_data)
#                     tasks.append(task)
#                 redis_tasks[set_name] = {
#                     "queue_name": set_name,
#                     "queue_length": set_length,
#                     "jobs": tasks
#                 }
#             else:
#                 redis_tasks[set_name] = {
#                         "queue_name": set_name,
#                         "queue_length": set_length,
#                         "jobs": []
#                     }
#         except redis.exceptions.RedisError as e:
#             print(f"An error occurred with set '{set_name}': {e}")
    
#     return redis_tasks