
#from __future__ import print_function
import sys
sys.path.append('../gelib')
sys.path.append('../gedef')
from kubernetes import client, config
import json
from operator import itemgetter
from flask import Flask, request, render_template, redirect, url_for
from werkzeug.utils import secure_filename
from flask import send_from_directory
import os
import threading, time
import uuid 
import GE_define as gDefine
import GE_GSCH_define as gschDefine
import GE_kubernetes as gKube
import GE_platform_util as pUtil
from GE_GSCH_request_job import RequestJob
from GE_redis import redisController
from GE_GSCH_queue import RequestQueue
from GE_GSCH_policy_scale_controller import policyScaleController
from GE_meta_data import metaData
from kafka import KafkaProducer
from kafka import KafkaConsumer
from kafka.admin import KafkaAdminClient, NewTopic
from json import loads 
import shutil
import yaml
import ast
import requests

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

try :
    config.load_incluster_config()
except:
    config.load_kube_config()
v1 = client.CoreV1Api()

GE_metaData               = metaData()
GE_RequestQueue           = RequestQueue()
GE_policyScaleController  = policyScaleController(gschDefine.GLOBAL_SCHEDULER_POLICY_YAML_PATH)
gRedis                    = redisController()
PREFIX = '/GEP/GSCH'
'''-------------------------------------------------------------------------------------------------------
            INIT GSCH SERVER
-------------------------------------------------------------------------------------------------------'''
def init_gsch_gsch_server():
    
    # set ##global define data
    '''------------------------------------------------
            KAFKA MESSAGE
    ------------------------------------------------'''
    while 1:     
        r = pUtil.find_service_from_platform_service_list_with_k8s(gDefine.GEDGE_SYSTEM_NAMESPACE,gDefine.KAFKA_SERVICE_NAME)
        if r : 
            gDefine.KAFKA_ENDPOINT_IP   = r['access_host']
            gDefine.KAFKA_ENDPOINT_PORT = r['access_port']
            gDefine.KAFKA_SERVER_URL            = str(gDefine.KAFKA_ENDPOINT_IP)+str(':')+str(gDefine.KAFKA_ENDPOINT_PORT)
            print(gDefine.KAFKA_ENDPOINT_IP,gDefine.KAFKA_ENDPOINT_PORT)
            break
        else :
            print('wait for running platform service',)
            time.sleep(gDefine.WAIT_RUNNING_PLATFORM_SERVICES_SECOND_TIME) 
            continue

    '''-----------------------------------------------
            REDIS
    -----------------------------------------------'''
    while 1:
        r = pUtil.find_service_from_platform_service_list_with_k8s(gDefine.GEDGE_SYSTEM_NAMESPACE,gDefine.REDIS_SERVICE_NAME)
        if r : 
            gDefine.REDIS_ENDPOINT_IP   = r['access_host']
            gDefine.REDIS_ENDPOINT_PORT = r['access_port']
            print(gDefine.REDIS_ENDPOINT_IP,gDefine.REDIS_ENDPOINT_PORT)
            break
        else :
            print('wait for running platform service',)
            time.sleep(gDefine.WAIT_RUNNING_PLATFORM_SERVICES_SECOND_TIME) 
            continue

    '''-----------------------------------------------
            MONGO DB 
    -----------------------------------------------'''
    while 1:        
        r = pUtil.find_service_from_platform_service_list_with_k8s(gDefine.GEDGE_SYSTEM_NAMESPACE,gDefine.MONGO_DB_SERVICE_NAME)
        if r : 
            gDefine.MONGO_DB_ENDPOINT_IP   = r['access_host']
            gDefine.MONGO_DB_ENDPOINT_PORT = r['access_port']
            print(gDefine.MONGO_DB_ENDPOINT_IP,gDefine.MONGO_DB_ENDPOINT_PORT)    
            print('3')
            break
        else :
            print('wait for running platform service',)
            time.sleep(gDefine.WAIT_RUNNING_PLATFORM_SERVICES_SECOND_TIME) 
            continue
    '''-----------------------------------------------
            KAFKA
    -----------------------------------------------''' 
    # make KafkaAdminClient
    kafka_admin_client = KafkaAdminClient( bootstrap_servers=gDefine.KAFKA_SERVER_URL, client_id='test')
    
    # create topic of GEDGE_GLOBAL_GSCH_TOPIC_NAME
    try :  
        topic_list = []
        print('1')
        topic_list.append(NewTopic(name=gDefine.GEDGE_GLOBAL_GSCH_TOPIC_NAME, num_partitions=1, replication_factor=1))
        print('2')
        kafka_admin_client.create_topics(new_topics=topic_list, validate_only=False)
        print('3')
        print('topic is created:', gDefine.GEDGE_GLOBAL_GSCH_TOPIC_NAME)
    except:
        print('topic is exist',gDefine.GEDGE_GLOBAL_GSCH_TOPIC_NAME)

'''-------------------------------------------------------------------------------------------------------
            INIT GSCH SERVER
-------------------------------------------------------------------------------------------------------'''

def set_platform_gsch_policy_list_by_support_policy_dic(gemetadata, support_policy_list,support_policy_dic):
    gemetadata.drop_platform_gsch_policy_info()
    for support_policy in support_policy_list :
        set_data_dic = {}
        set_data_dic = support_policy_dic[support_policy]
        set_data_dic['policy_name']=support_policy
        print('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^')
        print('set_data_dic',set_data_dic)
        print('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^')
        gemetadata.set_platform_gsch_policy(set_data_dic)

'''-------------------------------------------------------------------------------------------------------
           REST API
-------------------------------------------------------------------------------------------------------'''

def rest_API_service():
    app.run(host='0.0.0.0', port=8787, threaded=True)

def list_pod():
    print("Listing pods with their IPs:")
    ret = v1.list_pod_for_all_namespaces(watch=False)
    for i in ret.items:
        print("%s\t%s\t%s" %
              (i.status.pod_ip, i.metadata.namespace, i.metadata.name))

@app.route('/test', methods=['GET','POST'])
def test():
    #print(request.get_json())
    response_data = {}
    response_data['Result'] = "test" 
    response = app.response_class(response=json.dumps(response_data), status=200, mimetype='application/json')
    gDefine.logger.info('test')
    return response

@app.route(f'{PREFIX}/page/low',methods=['GET','POST'])
def create_html_request_queue_insert_page_low():
    # get meta data of cluster information(GS Front Server IP, cluster name)
    # change template upload html with 
    return render_template("new-request-job-low.html")

@app.route(f'{PREFIX}/page/most',methods=['GET','POST'])
def create_html_request_queue_insert_page_most():
    # get meta data of cluster information(GS Front Server IP, cluster name)
    # change template upload html with 
    return render_template("new-request-job-most.html")

@app.route(f'{PREFIX}/page/select',methods=['GET','POST'])
def create_html_request_queue_insert_page_select():
    # get meta data of cluster information(GS Front Server IP, cluster name)
    # change template upload html with 
    return render_template("new-request-job-select.html")

@app.route(f'{PREFIX}/test/low', methods=['POST'])
def create_scheduling_job_low():
    try :
        if request.method == "POST":
            f = request.files['yaml_file']
            fileID = uuid.uuid4()
            uuid_dir = fileID

            uploads_dir = str(gschDefine.GLOBAL_SCHEDULER_UPLOAD_PATH)+str('/')+str(uuid_dir)
            print("dir:",uploads_dir)
            os.makedirs(uploads_dir,exist_ok=True)
            f.save(os.path.join(uploads_dir, secure_filename(f.filename)))
            ff = open(uploads_dir+str('/')+str(f.filename), "rb")
            file_data = ff.read()
            ff.close()
            # save yaml file with key at Redis Server
            result = gRedis.hset_data_to_redis(file_data, gDefine.REDIS_YAML_KEY)
            print('hset_data_to_redis',result)
            # delete temp directory 
            if result != None :
                try:
                    shutil.rmtree(uploads_dir)
                    print('deleted temp directory',uploads_dir)
                except OSError as e:
                    print ("Error: %s - %s." % (e.filename, e.strerror))

            selected_clusters_data = request.values.get("selected_clusters")

            print("type selected_clusters:",type(selected_clusters_data))
            print("selected_clusters:",selected_clusters_data)
            selected_clusters_list = ast.literal_eval(selected_clusters_data)
            print("type selected_clusters_list:",type(selected_clusters_list))
            print("selected_clusters_list:",selected_clusters_list)

            fast_option = request.values.get("fast_option")
            print("fast_option:",fast_option)
            source_cluster = request.values.get("source_cluster")
            print("source_cluster:",source_cluster)
            source_node = request.values.get("source_node")
            print("source_node:",source_node)
            temp_env={'type':'##global','targetClusters':selected_clusters_list ,'priority':'GLowLatencyPriority',
                    'option': {'sourceCluster':source_cluster,'sourceNode':source_node}
            }
            print("temp_env:",temp_env)
          
            temp_RequestJob=RequestJob(fileID=result[1],env=temp_env) 
          
            if fast_option == 'fast' :
                GE_RequestQueue.insert_RequestJob(request_job=temp_RequestJob,option='fast')
            else :
                GE_RequestQueue.insert_RequestJob(request_job=temp_RequestJob)
          
            response_data = {}
            response_data['Result'] = "requestID:" + str(temp_RequestJob.requestID)
            response = app.response_class(response=json.dumps(response_data), status=200, mimetype='application/json')
            gDefine.logger.info('Success : create_scheduling_job ')
            return response
        else :
            return response_wihterror('ServiceInternalException', 'error: create_scheduling_job') 
    except:
        return response_wihterror('ServiceInternalException', 'error: create_scheduling_job') 

@app.route(f'{PREFIX}/test/most', methods=['POST'])
def create_scheduling_job_most():
    try :
        if request.method == "POST":
            f = request.files['yaml_file']
            print("o-1")
            fileID = uuid.uuid4()
            uuid_dir = fileID
            print("o-2")

            uploads_dir = str(gschDefine.GLOBAL_SCHEDULER_UPLOAD_PATH)+str('/')+str(uuid_dir)
            print("o-3")
            print("dir:",uploads_dir)
            os.makedirs(uploads_dir,exist_ok=True)
            print("o-4")
            f.save(os.path.join(uploads_dir, secure_filename(f.filename)))
            ff = open(uploads_dir+str('/')+str(f.filename), "rb")
            file_data = ff.read()
            ff.close()
            print("o-5")  
            # save yaml file with key at Redis Server
            result = gRedis.hset_data_to_redis(file_data, gDefine.REDIS_YAML_KEY)
            print('hset_data_to_redis',result)
            # delete temp directory 
            if result != None :
                try:
                    shutil.rmtree(uploads_dir)
                    print('deleted temp directory',uploads_dir)
                except OSError as e:
                    print ("Error: %s - %s." % (e.filename, e.strerror))

            selected_clusters_data = request.values.get("selected_clusters")
            print("type selected_clusters:",type(selected_clusters_data))
            print("selected_clusters:",selected_clusters_data)
            selected_clusters_list = ast.literal_eval(selected_clusters_data)
            print("type selected_clusters_list:",type(selected_clusters_list))
            print("selected_clusters_list:",selected_clusters_list)
            
            fast_option = request.values.get("fast_option")
            print("fast_option:",fast_option)
            
            temp_env={'type':'##global','targetClusters': selected_clusters_list,'priority':'GMostRequestedPriority' }
            
                
            print("o-6")                  
            temp_RequestJob=RequestJob(fileID=result[1],env=temp_env) 
            print("o-7")
            if fast_option == 'fast' :
                GE_RequestQueue.insert_RequestJob(request_job=temp_RequestJob,option='fast')
            else :
                GE_RequestQueue.insert_RequestJob(request_job=temp_RequestJob)
            
            print("o-8")
            response_data = {}
            response_data['Result'] = "requestID:" + str(temp_RequestJob.requestID)
            response = app.response_class(response=json.dumps(response_data), status=200, mimetype='application/json')
            gDefine.logger.info('Success : create_scheduling_job ')
            return response
        else :
            return response_wihterror('ServiceInternalException', 'error: create_scheduling_job')
    except:
        return response_wihterror('ServiceInternalException', 'error: create_scheduling_job')


@app.route(f'{PREFIX}/test/select', methods=['POST'])
def create_scheduling_job_select():
    try :
        if request.method == "POST":
            f = request.files['yaml_file']
            print("o-1")
            fileID = uuid.uuid4()
            uuid_dir = fileID
            print("o-2")

            uploads_dir = str(gschDefine.GLOBAL_SCHEDULER_UPLOAD_PATH)+str('/')+str(uuid_dir)
            print("o-3")
            print("dir:",uploads_dir)
            os.makedirs(uploads_dir,exist_ok=True)
            print("o-4")
            f.save(os.path.join(uploads_dir, secure_filename(f.filename)))
            ff = open(uploads_dir+str('/')+str(f.filename), "rb")
            file_data = ff.read()
            ff.close()
            print("o-5")  
            # save yaml file with key at Redis Server
            result = gRedis.hset_data_to_redis(file_data, gDefine.REDIS_YAML_KEY)
            print('hset_data_to_redis',result)
            # delete temp directory 
            if result != None :
                try:
                    shutil.rmtree(uploads_dir)
                    print('deleted temp directory',uploads_dir)
                except OSError as e:
                    print ("Error: %s - %s." % (e.filename, e.strerror))

            selected_clusters_data = request.values.get("selected_clusters")
            print("type selected_clusters:",type(selected_clusters_data))
            print("selected_clusters:",selected_clusters_data)
            selected_clusters_list = ast.literal_eval(selected_clusters_data)
            print("type selected_clusters_list:",type(selected_clusters_list))
            print("selected_clusters_list:",selected_clusters_list)

            fast_option = request.values.get("fast_option")
            print("fast_option:",fast_option)
    
            temp_env={'type':'##global','targetClusters': selected_clusters_list,'priority':'GSelectedCluster' }
            print("temp_env:",temp_env)
            
            print("o-6")                  
            temp_RequestJob=RequestJob(fileID=result[1],env=temp_env) 
            print("o-7")
            if fast_option == 'fast' :
                GE_RequestQueue.insert_RequestJob(request_job=temp_RequestJob,option='fast')
            else :
                GE_RequestQueue.insert_RequestJob(request_job=temp_RequestJob)
            
            print("o-8")
            response_data = {}
            response_data['Result'] = "requestID:" + str(temp_RequestJob.requestID)
            response = app.response_class(response=json.dumps(response_data), status=200, mimetype='application/json')
            gDefine.logger.info('Success : create_scheduling_job ')
            return response
        else :
            return response_wihterror('ServiceInternalException', 'error: create_scheduling_job') 
    except:
        return response_wihterror('ServiceInternalException', 'error: create_scheduling_job') 


'''-------------------------------------------------------------------------------------------------------
            DISPATCH REQUEST
-------------------------------------------------------------------------------------------------------'''

@app.route(f'{PREFIX}/dispatchedqueue/policies/<policy>', methods=['GET'])
def schedule_dispatched_request(policy):
    '''-------------------------------
    dictionary = {'george': 16, 'amber': 19}
    search_age = input("Provide age")
    for name, age in dictionary.items():  # for name, age in dictionary.iteritems():  (for Python 2.x)
       if age == search_age:
          print(name)
    ---------------------------------'''
    
    if GE_RequestQueue.get_dispatched_queue_size() <= 0 :
        return response_wihterror('ServiceInternalException', 'error: pull_dispatched_request: empty') 
    print('dispatchedQueue-----------------------------------------')            
    for request_id, request_job in GE_RequestQueue.dispatchedQueue.items():
        print('request_id:',request_id) 
        print('request_job.status',request_job.status)
    print('dispatchedQueue-----------------------------------------')    
    for request_id, request_job in GE_RequestQueue.dispatchedQueue.items():
        if request_job.env['priority'] == str(policy) and request_job.status == 'dispatched' :
           print('request_id:',request_id,' is scheduling') 
           print('request_job.env',request_job.env)
           response_data = request_job.toJson()
           response = app.response_class(response=json.dumps(response_data), status=200, mimetype='application/json')
           GE_RequestQueue.dispatchedQueue[request_id].status = 'scheduling'
           # del GE_RequestQueue.pop_dispatched_queue(request_id)
           gDefine.logger.info('pull_dispatched_request')
           return response
    return response_wihterror('ServiceInternalException', 'error: pull_dispatched_request: empty'+str(policy)) 

'''-------------------------------------------------------------------------------------------------------
            REQUEST
-------------------------------------------------------------------------------------------------------'''
@app.route(f'{PREFIX}/dispatchedqueue/requestjobs/<request_id>/status', methods=['GET','PUT'])
def dispatched_queue_status(request_id):
    print('start dispatched_queue_status')
    response_data = {}
    if request.method == 'GET':
       response_data['Result'] = GE_RequestQueue.dispatchedQueue[request_id].status
       response = app.response_class(response=json.dumps(response_data), status=200, mimetype='application/json')
       gDefine.logger.info('get : dispatched_queue_status')
       return response
    elif request.method == 'PUT':
        try :
            changed_status = request.args.get('changed_status')
        except:
             return response_wihterror('InvalidRequestContentException', 'error: update : dispatched_queue_status')
        if changed_status == 'failed':
            GE_RequestQueue.dispatchedQueue[request_id].increaseFailCnt()
            if GE_RequestQueue.dispatchedQueue[request_id].failCnt > gschDefine.GLOBAL_SCHEDULER_MAX_FAIL_CNT :
                GE_RequestQueue.pop_dispatched_queue(request_id) 
                print("delete Job")
                result_str='failCnt is over GLOBAL_SCHEDULER_MAX_FAIL_CNT'
            elif GE_RequestQueue.dispatchedQueue[request_id].failCnt > gschDefine.GLOBAL_SCHEDULER_FIRST_FAIL_CNT :
                GE_RequestQueue.firstQueue.put(GE_RequestQueue.pop_dispatched_queue(request_id))
                result_str='instert job into first Queue'
            else :
                GE_RequestQueue.baseQueue.put(GE_RequestQueue.pop_dispatched_queue(request_id))
                result_str='fail count is increased'
        elif changed_status == 'canceled':
            GE_RequestQueue.pop_dispatched_queue(request_id)
            result_str='this jod is canceled' 
        elif changed_status == 'completed':
            GE_RequestQueue.pop_dispatched_queue(request_id)
            result_str='this jod is completed'  
        else :
            print('error: format')
            print('end update_dispatched_queue_status',result_str)
            return response_wihterror('InvalidRequestContentException', 'error: update : dispatched_queue_status') 
        
        response_data['Result'] = result_str
        response = app.response_class(response=json.dumps(response_data), status=200, mimetype='application/json')
        gDefine.logger.info('update : dispatched_queue_status')
        return response
    else :
        return response_wihterror('MethodNotAllowed', 'error: dispatched_queue_status')
'''-------------------------------------------------------------------------------------------------------
        POLICY 
-------------------------------------------------------------------------------------------------------'''
@app.route(f'{PREFIX}/policys/<policy_name>/replicas', methods=['GET','PUT'])
def policy_scale(policy_name):
    response_data = {}
    if request.method == 'PUT':
        print('start update_policy_scale')
        replicas = request.args.get('replicas_size')
        result   = GE_policyScaleController.set_policy_scale_by_update_deployment(policy_name,replicas)
        if result :
            response_data['Result'] = result
            response = app.response_class(response=json.dumps(response_data), status=200, mimetype='application/json')
            gDefine.logger.info('update_policy_scale')
            return response
        else :
            return response_wihterror('ServiceInternalException', 'error: update_policy_scale:'+str(policy_name)) 
    elif request.method == 'GET':
        response_data['Result'] = GE_policyScaleController.get_replica_size_by_policy_name(policy_name)
        response = app.response_class(response=json.dumps(response_data), status=200, mimetype='application/json')
        gDefine.logger.info('get_policy_scale_size')
        return response
    else :
        return response_wihterror('MethodNotAllowed', 'error: policy_scale') 
    
@app.route(f'{PREFIX}/policyNameList', methods=['GET'])
def get_policy_name_list():
    print('start get_policy_name_list')
    
    response_data = {}
    if request.method == 'GET':
        result = GE_policyScaleController.get_policy_name_list()
        if result :
            response_data['Result'] = result
            response = app.response_class(response=json.dumps(response_data), status=200, mimetype='application/json')
            gDefine.logger.info('get_policy_name_list')
            return response
        else :
            return response_wihterror('ServiceInternalException', 'error: get_policy_name_list:') 
    else :
        return response_wihterror('MethodNotAllowed', 'error: get_policy_name_list') 
    
'''-------------------------------------------------------------------------------------------------------
           RESPONSE
-------------------------------------------------------------------------------------------------------'''
def response_wihterror(ErrorCode, DetailLog):
    print(DetailLog)
    response_data = {}
    response_data['Error'] = {}
    response_data['Error']['ErrorCode'] = ErrorCode
    response_data['Error']['Message'] = gDefine.ERROR_CODES[ErrorCode]['Description']
    response = app.response_class(response=json.dumps(response_data), 
            status=gDefine.ERROR_CODES[ErrorCode]['StatusCode'], mimetype='application/json')
    gDefine.logger.error(response_data)
    return response

'''-------------------------------------------------------------------------------------------------------
        REQUEST JOBS policyScaleController THREAD 
-------------------------------------------------------------------------------------------------------'''
def policy_scale_controller_service():
    cnt = 0
    print('policy_scale_controller_service')
    '''
    ['GLowLatencyPriority','GMostRequestedPriority','GSelectedCluster']
    policy_metrics=  { GLowLatencyPriority    : 0,
                       GMostRequestedPriority : 0,
                       GSelectedCluster       : 0  }  

    '''
    policy_metrics={}

    # init policy_metrics
    for p in GE_policyScaleController.support_policy_list :
        policy_metrics[p] =0

    while True: 
        # monitor get_total_queue_size / policy count 
        # update the scale of each policy deployment 
        for p in GE_policyScaleController.support_policy_list :
            policy_metrics[p] = 0
        for request_id, request_job in GE_RequestQueue.dispatchedQueue.items():
            print( request_id,request_job.env['priority'],request_job.status) 
            if request_job.status == 'dispatched' :
               policy_metrics[request_job.env['priority']] += 1
        print('policy_metrics',policy_metrics)
        time.sleep(5)

if __name__ == '__main__':
    init_gsch_gsch_server()
    #support_policy_list = ['GLowLatencyPriority','GMostRequestedPriority','GSelectedCluster']
    GE_metaData.init_platform_metadata_from_mongodb(ip=gDefine.MONGO_DB_ENDPOINT_IP,port=int(gDefine.MONGO_DB_ENDPOINT_PORT))
    set_platform_gsch_policy_list_by_support_policy_dic(GE_metaData,GE_policyScaleController.support_policy_list, GE_policyScaleController.support_policy_dic)
    gRedis.connect_redis_server(gDefine.REDIS_ENDPOINT_IP,gDefine.REDIS_ENDPOINT_PORT)
    
    '''-------------------------------------------------------------------------------------------------------
           REST API THREAD 
    -------------------------------------------------------------------------------------------------------'''
    t1 = threading.Thread(target=rest_API_service)
    t1.daemon = True 
    t1.start()

    '''-------------------------------------------------------------------------------------------------------
           REQUEST JOBS policyScaleController THREAD 
    -------------------------------------------------------------------------------------------------------'''    
    t2 = threading.Thread(target=policy_scale_controller_service)
    t2.daemon = True 
    t2.start()

    '''-------------------------------------------------------------------------------------------------------
           REQUEST JODS DISPATCHER
    -------------------------------------------------------------------------------------------------------'''
    cnt=0
    
    while True: 
        if len(GE_RequestQueue.dispatchedQueue) < gschDefine.GLOBAL_SCHEDULER_MAX_DISPATCH_SIZE :
            GE_RequestQueue.dispatch_RequestJob()
            print("dispatch_RequestJob:",cnt)
            print(GE_RequestQueue.dispatchedQueue)
        else :
            print("dispatch_RequestJob buffer is fulled")
        cnt=cnt+1
        time.sleep(5)
