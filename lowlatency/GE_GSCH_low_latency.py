import sys
sys.path.append('../gelib')
sys.path.append('../gedef')
import GE_define as gDefine
import GE_GSCH_low_define as lowDefine
import GE_kubernetes as gKube
import GE_platform_util as pUtil
from kafka import KafkaProducer
from kafka import KafkaConsumer
from kafka import KafkaAdminClient
import json
from json import dumps
from json import loads 
import time 
import os
import requests
import sys
import urllib


PREFIX = '/GEP/GSCH'

def init_gsch_low_policy():
    
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
                GSCH SERVER
    -----------------------------------------------'''
    while(1) :
        r = pUtil.find_service_from_platform_service_list_with_k8s(gDefine.GEDGE_SYSTEM_NAMESPACE,gDefine.GSCH_SERVER_SERVICE_NAME)
        if r : 
            lowDefine.GSCH_SERVER_ENDPOINT_IP   = r['access_host']
            lowDefine.GSCH_SERVER_ENDPOINT_PORT = r['access_port']
            lowDefine.GSCH_SERVER_URL      = str('http://')+str(lowDefine.GSCH_SERVER_ENDPOINT_IP)+str(':')+str(lowDefine.GSCH_SERVER_ENDPOINT_PORT)
            print(lowDefine.GSCH_SERVER_ENDPOINT_IP ,lowDefine.GSCH_SERVER_ENDPOINT_PORT)    
            break
        else:
            print('wait',gDefine.GSCH_SERVER_SERVICE_NAME)
            time.sleep(gDefine.WAIT_RUNNING_PLATFORM_SERVICES_SECOND_TIME)
            continue

init_gsch_low_policy()

GE_request_job = None 

'''
{'requestID': 'req-f6720a0e-e3df-455a-825d-f8c80cedc2d9', 
 'date': '2021-10-18 13:46:30', 'status': 'create', 
 'fileID': 'b469e54a-721f-4c55-b43e-d09088556031', 'failCnt': 0, 
 'env': {
         'type': 'global', 
         'targetClusters': ['c1', ['c2', 'c3'], 'c4'], 
         'priority': 'GLowLatencyPriority', 
         'option': {
             'sourceCluster': 'c1', 
             'sourceNode': 'a-worker-node01'
          }
        }
}
'''
class GLowLatencyPriority_Job:
    def __init__(self,request_data_dic):
        self.job_name       = lowDefine.SELF_POLICY_NAME
        self.requestDataDic = request_data_dic
        self.requestID      = request_data_dic['requestID']
        self.fileID         = request_data_dic['fileID']
        self.failCnt        = request_data_dic['failCnt']
       
        self.env            = request_data_dic['env']
        self.targetClusters = self.env['targetClusters'] 
        self.sourceCluster  = self.env['option']['sourceCluster']
        self.sourceNode     = self.env['option']['sourceNode']
        self.producer       = KafkaProducer(acks=0,compression_type='gzip', 
                              bootstrap_servers=[gDefine.KAFKA_SERVER_URL], 
                              value_serializer=lambda x: dumps(x).encode('utf-8')) 
                
    def check_for_fault_response_msg(self, res):
        if res == None:
            return True
        if 'hcode' not in res:
            return True
        if 'lcode' not in res:
            return True
        if 'msg' not in res:
            return True
        if 'result' not in res['msg']:
            return True
        return False

    def send_clusters_latency_request_msg_to_cluster_agents(self,clusters):
        try :
            clusters_latency_request_msg = {'source':{'type':'none'},
                'target':{'type':'cluster', 'object':self.sourceCluster},
                'hcode':200,
                'lcode':1,
                'msg':{'requestID': self.requestID,'sourceNode': self.sourceNode,'targetClusters': clusters }
                }
            self.producer.send(gDefine.GEDGE_GLOBAL_GSCH_TOPIC_NAME,value=clusters_latency_request_msg)
            self.producer.flush()
        except:
            return 'process_fail'
        return 'process_success'

    def wait_clusters_latency_response_msg_from_cluster_agents(self):
        ordered_cluster_list =[]
        res = self.wait_response_msg_from_request_id_topic()
        if res == None:
            print('res is None')
            return 'process_fail', ordered_cluster_list
        is_process_fail = self.check_for_fault_response_msg(res)

        hcode = res['hcode']
        lcode = res['lcode']
        result = res['msg']['result']
        '''
        result: [ {cluster: c3, latency: 11 },
                  {cluster: c2, latency: 34 } ]
        '''
        if is_process_fail:
            print('Fail Job:', res)
            return 'process_fail', ordered_cluster_list
        else:
            if hcode == 200 and lcode == 2 :
                for t_cluster in result :
                    ordered_cluster_list.append(t_cluster['cluster'])
                return 'process_success', ordered_cluster_list 
            else:
                return 'process_fail', ordered_cluster_list 

    def send_apply_yaml_request_msg_to_cluster_agent(self,cluster):
        print('send_apply_yaml_request_msg_to_cluster_agent:',cluster)
        try :
            print('1')
            apply_yaml_msg = {'source':{'type':'none'},
                'target':{'type':'cluster', 'object':cluster},
                'hcode':210,
                'lcode':1,
                'msg':{'requestID': self.requestID,'fileID':self.fileID,'requestData':self.requestDataDic }
            }
            print('2')
            self.producer.send(gDefine.GEDGE_GLOBAL_GSCH_TOPIC_NAME,value=apply_yaml_msg)
            print('3')
            self.producer.flush()
            print('4')
        except:
            return 'process_fail'
        return 'process_success'

    def wait_response_msg_of_apply_yaml_request_from_cluster_agents(self):
        res = self.wait_response_msg_from_request_id_topic()
        if res == None:
            print('res is None')
            return 'process_fail'
        is_process_fail = self.check_for_fault_response_msg(res)

        hcode = res['hcode']
        lcode = res['lcode']
        result = res['msg']['result']
        
        print('hcode :hcode,result',hcode,lcode,result)

        if is_process_fail:
            print('Fail Job:', res)
            return 'process_fail'
        else:
            if hcode == 210 and lcode == 2:
                if result == 'success' :
                    return 'apply_success'
                elif result == 'fail' :
                    return 'apply_fail'
                elif result == 'cancel' :
                    return 'cancel'
                else :
                    return 'process_fail'
            else:
                return 'process_fail'

    def wait_response_msg_from_request_id_topic(self):
        print('wait_response_msg_from_request_id_topic')
        consumer = KafkaConsumer( 
                self.requestID, 
                bootstrap_servers=[gDefine.KAFKA_SERVER_URL], 
                auto_offset_reset='earliest', 
                enable_auto_commit=True, 
                group_id=self.requestID, 
                value_deserializer=lambda x: loads(x.decode('utf-8')), 
                consumer_timeout_ms=lowDefine.CONSUMER_TIMEOUT_MS_TIME
        )
        print('w-1')
        res = None
        for message in consumer: 
            print("Topic: %s, Partition: %d, Offset: %d, Key: %s, Value: %s" % ( message.topic, message.partition, message.offset, message.key, message.value )) 
            res = message.value
            break
        consumer.close()
        return res

def read_dispatched_queue():
    t_GE_request_job = None 

    REQUEST_DISPATCH_QUEUE_URL = lowDefine.GSCH_SERVER_URL+f'{PREFIX}/dispatchedqueue/policies/'+lowDefine.SELF_POLICY_NAME

    while 1 :
        try :
            res = requests.get(REQUEST_DISPATCH_QUEUE_URL)
        except:
            print('wait gsch server to run',lowDefine.GSCH_SERVER_URL)
            time.sleep(lowDefine.REQUEST_DISPATCH_RETRY_DELAY_SECOND_TIME) 
            continue
        if res.status_code == 200 :
            print('2')
            request_data_dic = json.loads(res.json())
            print('request_data_dic',request_data_dic)
            t_GE_request_job = GLowLatencyPriority_Job(request_data_dic) 
            print('3')
            break 
        else :
            print('despatched queue is empty')
            time.sleep(lowDefine.READ_DISPATCH_QUEUE_RETRY_DELAY_SECOND_TIME) 
            continue
    return t_GE_request_job

def request_job_processor():
    global GE_request_job
    print('request_job_processor')
    while 1 :
        #read Request_Job from dispatched queue
        GE_request_job = read_dispatched_queue()
        '''
        return values 
            'process_success' :
            'process_fail': raise error in process(apply or wait consumer, request latency) 
            'apply_success' : apply is success
            'apply_fail' : apply is fail 
        '''
        is_whole_process_status = None
        for t_cluster in GE_request_job.targetClusters :
            print('type(t_cluster)',type(t_cluster),t_cluster)
            if type(t_cluster).__name__ == 'list' and len(t_cluster) > 1 :
                r = GE_request_job.send_clusters_latency_request_msg_to_cluster_agents(t_cluster)
                if r == 'process_fail' :
                    print('internal error : send_clusters_latency_request_msg_to_cluster_agents')
                    continue
                r,sorted_clusters = GE_request_job.wait_clusters_latency_response_msg_from_cluster_agents()
                if r == 'process_fail' :
                    print('internal error : wait_clusters_latency_response_msg_from_cluster_agents')
                    continue
                for t2_cluster in sorted_clusters:
                    r = GE_request_job.send_apply_yaml_request_msg_to_cluster_agent(t2_cluster)
                    if r == 'process_fail' :
                        print('internal error : send_apply_yaml_request_msg_to_cluster_agent')
                        continue
                    r = GE_request_job.wait_response_msg_of_apply_yaml_request_from_cluster_agents()
                    if r == 'process_fail' :
                        print('internal error : wait_response_msg_of_apply_yaml_request_from_cluster_agents')
                        continue
                    elif r == 'apply_success' or r == 'cancel':
                        print('---apply_success or cancel',r)
                        is_whole_process_status = r
                        break
                    elif r == 'apply_fail' :
                        is_whole_process_status = r
                        continue
                if r == 'apply_success' or r == 'cancel':
                    break
            else :
                r = GE_request_job.send_apply_yaml_request_msg_to_cluster_agent(t_cluster)
                if r == 'process_fail' :
                    print('internal error : send_apply_yaml_request_msg_to_cluster_agent')
                    continue
                r = GE_request_job.wait_response_msg_of_apply_yaml_request_from_cluster_agents()
                if r == 'process_fail' :
                    print('internal error : wait_response_msg_of_apply_yaml_request_from_cluster_agents')
                    continue
                elif r == 'apply_success' or r == 'cancel':
                    is_whole_process_status = r
                    print('apply_success or cancel:',r)
                    break
                elif r == 'apply_fail':
                    is_whole_process_status = r
                    print('apply_fail')
                    continue
        print('==============')
        
        UPDATE_STATUS_OF_REQUEST_JOB_URL = lowDefine.GSCH_SERVER_URL+f'{PREFIX}/dispatchedqueue/requestjobs/'+GE_request_job.requestID+'/status'
        
        if is_whole_process_status == 'apply_fail' :
            params = {'changed_status': 'failed'}
        elif is_whole_process_status == 'apply_success' :
            params = {'changed_status': 'completed'}
        elif is_whole_process_status == 'cancel' :
            params = {'changed_status': 'canceled'}
        else :
            params = {'changed_status': 'canceled'}                
        query_string = urllib.urlencode(params)
        full_url = "{}?{}".format(UPDATE_STATUS_OF_REQUEST_JOB_URL, query_string)
        print(full_url)
        requests.put(full_url)
        
if __name__ == '__main__':
    request_job_processor()   

