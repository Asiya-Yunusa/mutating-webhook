from flask import Flask, request, jsonify
import base64
import jsonpatch
import logging
import os
import json

warden = Flask(__name__)

# set up logging to console
logging.basicConfig(level=logging.DEBUG)

# define a Handler which writes DEBUG messages or higher to the sys.stderr
console = logging.StreamHandler()
console.setLevel(logging.INFO)

# set a format which is simpler for console use
formatter = logging.Formatter('%(asctime)s:%(name)-12s: %(levelname)-8s %(message)s')

# tell the handler to use this format
console.setFormatter(formatter)

# add the handler to the root logger
root = logging.getLogger('')
root.addHandler(console)

#POST route for Admission Controller  
@warden.route('/mutate', methods=['POST'])
#Admission Control Logic
def deployment_webhook():
    # global variables
    global applicationName
    global spec
    global containers
    global springBoot
    global uid
    global annotations
    global dllFilename
    global main_spec
    
    # function variables
    annotations = ""
    installAppdagent = ""
    programmingLanguage = ""
    springBoot = ""
    dllFilename = ""
    
    request_info = request.get_json()
    
    logging.debug(request_info)

    metadata = request_info["request"]["object"]["metadata"]
    spec = request_info["request"]["object"]["spec"]
    containers = spec["template"]["spec"]["containers"][0]
    main_spec = spec["template"]["spec"]

    uid = request_info["request"].get("uid")
    applicationName = metadata["labels"].get("app")


    if "annotations" in metadata:
        logging.info('metadata has annotations')
        annotations = metadata["annotations"]

        if "monitoring/install-appdynamics-agent"  and "monitoring/programming-language" in annotations:
              installAppdagent = annotations.get("monitoring/install-appdynamics-agent")
              programmingLanguage = annotations.get("monitoring/programming-language")
        else:  
            message = "{} cannot be onboarded to appdynamics because the programming language annotation is not added. Please add the programming language annotation if you set installAppdagent annotation to true".format(applicationName)
            logging.info(message)

            language_annotation_patch = [{"op": "add","path": "/metadata/annotations/appdagent", "value": " not installed"},
            {"op": "add","path": "/metadata/annotations/appdagent-reason", "value": "Programming language annotation is not present"}
            ]
 
            language_annotation_patch = jsonpatch.JsonPatch(language_annotation_patch)
        
            base64_patch = base64.b64encode(language_annotation_patch.to_string().encode("utf-8")).decode("utf-8")
 
            return jsonify({"apiVersion": "admission.k8s.io/v1", "kind": "AdmissionReview", "response": {"allowed": True, "uid": uid, "status": {"message": message}, "patchType": "JSONPatch", "patch": base64_patch}})

        if programmingLanguage == "dotnet" :
              dllFilename = annotations.get("monitoring/dll-filename")

    if  programmingLanguage == "dotnet" and "monitoring/dll-filename" not in annotations:

        message = "{} cannot be onboarded to appdynamics because the dll-filename annotation is not added for the dotnet application to be started. Please add the dll-filename annotation annotation if you set programming language annotation to dotnet".format(applicationName)
        logging.info(message)

        dll_filename_annotation_patch = [{"op": "add","path": "/metadata/annotations/appdagent", "value": " not installed"},
        {"op": "add","path": "/metadata/annotations/appdagent-reason", "value": "Dll-filename annotation is not present"}
        ]

        dll_filename_annotation_patch = jsonpatch.JsonPatch(dll_filename_annotation_patch)
    
        base64_patch = base64.b64encode(dll_filename_annotation_patch.to_string().encode("utf-8")).decode("utf-8")

        return jsonify({"apiVersion": "admission.k8s.io/v1", "kind": "AdmissionReview", "response": {"allowed": True, "uid": uid, "status": {"message": message}, "patchType": "JSONPatch", "patch": base64_patch}})


    if "monitoring/springboot-application" in annotations:
            springBoot = annotations.get("monitoring/springboot-application")

    if springBoot == "true" and programmingLanguage == "dotnet":
        message = "{} cannot be onboarded to appdynamics because the programming language annotation and springboot option do not match. Please add the correct  annotations according to the documented process".format(applicationName)
        logging.info(message)

        annotation_error_patch = [{"op": "add","path": "/metadata/annotations/appdagent", "value": " not installed"},
        {"op": "add","path": "/metadata/annotations/appdagent-reason", "value": "Programming language annotation and Springboot option do not match"}
        ]

        annotation_error_patch = jsonpatch.JsonPatch(annotation_error_patch)
    
        base64_patch = base64.b64encode(annotation_error_patch.to_string().encode("utf-8")).decode("utf-8")

        return jsonify({"apiVersion": "admission.k8s.io/v1", "kind": "AdmissionReview", "response": {"allowed": True, "uid": uid, "status": {"message": message}, "patchType": "JSONPatch", "patch": base64_patch}})
                            


    logging.info('Running webhook for: ' + applicationName )

    if installAppdagent == "true" and "appdagent" not in annotations:
        return k8s_response(uid, programmingLanguage)
    
    # send response back to controller to create object as is
    else:
        return jsonify({"apiVersion": "admission.k8s.io/v1", "kind": "AdmissionReview", "response": {"allowed": True, "uid": uid, "status": {"message": "Webhook not enabled"}}})


#Function to respond back to the Admission Controller for Java App
def k8s_response(uid, programmingLanguage):
    global argument
    global prefix
    global patch 

    prefix = "{}-".format(applicationName)
    dotnet_startup_command = "dotnet {}.dll".format(dllFilename)
    unique_host_id = "export APPDYNAMICS_AGENT_UNIQUE_HOST_ID=$(sed -rn '1s#.*/##; 1s/(.{12}).*/\\1/p' /proc/self/cgroup)"
    patch = []

    message = "Your application has been patched"

    # set appdynamics image depending on programming language
    if programmingLanguage == "java":
        appd_image = os.getenv('JAVA_AGENT')
        argument = "java -javaagent:/opt/appdynamics/javaagent.jar -jar /{}.jar".format(applicationName)
        patch = [{"op": "add","path": "/spec/template/spec/containers/0/env/-1","value": {"name": "APPDYNAMICS_JAVA_AGENT_REUSE_NODE_NAME", "value": "true"}},
        {"op": "add","path": "/spec/template/spec/containers/0/env/-1","value": {"name": "APPDYNAMICS_JAVA_AGENT_REUSE_NODE_NAME_PREFIX","value": prefix}},  
        {"op": "add","path": "/spec/template/spec/containers/0/env/-1","value": {"name": "APPDYNAMICS_NETVIZ_AGENT_HOST","valueFrom": {"fieldRef": {"apiVersion": "v1","fieldPath": "status.hostIP"}}}}, 
        {"op": "add","path": "/spec/template/spec/containers/0/env/-1","value": {"name": "APPDYNAMICS_AGENT_UNIQUE_HOST_ID","valueFrom": {"fieldRef": {"apiVersion": "v1","fieldPath": "spec.nodeName"}}}},
        {"op": "add","path": "/spec/template/spec/containers/-1/command", "value": ["/bin/sh"]},
        {"op": "add","path": "/spec/template/spec/containers/-1/args", "value": ["-c", argument]}]
 
    elif programmingLanguage == "dotnet":
        appd_image = os.getenv('DOTNET_AGENT')
        argument = "{0} && {1} ".format(unique_host_id, dotnet_startup_command)
        patch = [{"op": "add","path": "/spec/template/spec/containers/0/env/-1","value": {"name": "CORECLR_PROFILER","value": "{57e1aa68-2229-41aa-9931-a6e93bbc64d8}"}},
        {"op": "add","path": "/spec/template/spec/containers/0/env/-1","value": {"name": "CORECLR_ENABLE_PROFILING","value": "1"}},
        {"op": "add","path": "/spec/template/spec/containers/0/env/-1","value": {"name": "CORECLR_PROFILER_PATH","value": "/opt/appdynamics/libappdprofiler.so"}},
        {"op": "add","path": "/spec/template/spec/containers/0/env/-1","value": {"name": "APPDYNAMICS_AGENT_REUSE_NODE_NAME","value": "true"}},
        {"op": "add","path": "/spec/template/spec/containers/0/env/-1","value": {"name": "APPDYNAMICS_AGENT_REUSE_NODE_NAME_PREFIX","value": "prefix"}},
        {"op": "add","path": "/spec/template/spec/containers/0/env/-1","value": {"name": "LD_LIBRARY_PATH","value": "/opt/appdynamics"}},
        {"op": "add","path": "/spec/template/spec/volumes/-1","value": {"name": "appd-config","configMap": {"name": "appd-config"}}},
        {"op": "add","path": "/spec/template/spec/containers/0/volumeMounts/-1","value": {"name": "appd-config","subPath": "AppDynamicsConfig.json","mountPath": "/opt/appdynamics/AppDynamicsConfig.json"}}]

    else: 
        message = "{} cannot be onboarded to appdynamics because the programming langiuage is not valid".format(applicationName)
        logging.info(message)

        language_error_patch = [{"op": "add","path": "/metadata/annotations/appdagent", "value": " not installed"},
        {"op": "add","path": "/metadata/annotations/appdagent-reason", "value": "Programming language is not valid"}
        ]

        language_error_patch = jsonpatch.JsonPatch(language_error_patch)
        
        base64_patch = base64.b64encode(language_error_patch.to_string().encode("utf-8")).decode("utf-8")

        return jsonify({"apiVersion": "admission.k8s.io/v1", "kind": "AdmissionReview", "response": {"allowed": True, "uid": uid, "status": {"message": message}, "patchType": "JSONPatch", "patch": base64_patch}})


    # set index for volumes
    if "volumes" not in main_spec:
        volume = "/spec/template/spec/volumes"
        volumeValue = [{"name": "appd-agent-repo", "emptyDir": {}}]
    else:
        volume = "/spec/template/spec/volumes/-1"
        volumeValue = {"name": "appd-agent-repo", "emptyDir": {}}   

    # set index for initContainers
    if "initContainers" not in main_spec:
        initContainer = "/spec/template/spec/initContainers"
        initContainerValue = [{"command": ["cp","-ra","/opt/appdynamics/.","/opt/temp"],"image": appd_image ,"imagePullPolicy": "IfNotPresent","name": "appd-agent","volumeMounts": [{"mountPath": "/opt/temp","name": "appd-agent-repo"}]}]
    else:
        initContainer = "/spec/template/spec/initContainers/-1"
        initContainerValue = {"command": ["cp","-ra","/opt/appdynamics/.","/opt/temp"],"image": appd_image ,"imagePullPolicy": "IfNotPresent","name": "appd-agent","volumeMounts": [{"mountPath": "/opt/temp","name": "appd-agent-repo"}]}
 
    # set index for volumeMounts
    if "volumeMounts" not in containers:
        volumeMount = "/spec/template/spec/containers/0/volumeMounts"
        volumeMountValue = [{"mountPath": "/opt/appdynamics", "name": "appd-agent-repo"}]
    else:
        volumeMount = "/spec/template/spec/containers/0/volumeMounts/-1"
        volumeMountValue = {"mountPath": "/opt/appdynamics", "name": "appd-agent-repo"}

    # set index for environment varables
    if "env" not in containers:
        envVar = "/spec/template/spec/containers/0/env"
        envVarValue = [{"name": "APPDYNAMICS_AGENT_APPLICATION_NAME", "value": applicationName}]
    else:
        envVar = "/spec/template/spec/containers/0/env/-1"
        envVarValue = {"name": "APPDYNAMICS_AGENT_APPLICATION_NAME", "value": applicationName}

    # set index for environment varables reference
    if "envFrom" not in containers:
        envFrom = "/spec/template/spec/containers/0/envFrom"
        envFromValue = [{"configMapRef": {"name": "warden-config"}}]
    else:
        envFrom = "/spec/template/spec/containers/0/envFrom/-1"
        envFromValue = {"configMapRef": {"name": "warden-config"}}

    # check if a command exists on the manifests already and patch a error response
    if "command" in containers:
        message = "{} cannot be onboarded to appdynamics because there is an existing command to start the application".format(applicationName)
        logging.info(message)

        command_error_patch = [{"op": "add","path": "/metadata/annotations/appdagent", "value": " not installed"},
        {"op": "add","path": "/metadata/annotations/appdagent-reason", "value": "There is an existing command on the container"}]
        command_error_patch = jsonpatch.JsonPatch(command_error_patch)
        base64_patch = base64.b64encode(command_error_patch.to_string().encode("utf-8")).decode("utf-8")

        return jsonify({"apiVersion": "admission.k8s.io/v1", "kind": "AdmissionReview", "response": {"allowed": True, "uid": uid, "status": {"message": message}, "patchType": "JSONPatch", "patch": base64_patch}})
    

    # create json patch  
    json_patch = [ {"op": "add","path": "/metadata/annotations/appdagent", "value": "installed"},
       {"op": "add","path": volume, "value": volumeValue},
       {"op": "add","path": volumeMount, "value": volumeMountValue},
       {"op": "add","path": envVar, "value": envVarValue},
       {"op": "add","path": envFrom, "value": envFromValue},
       {"op": "add","path": "/spec/template/spec/containers/0/env/-1","value": {"name": "APPDYNAMICS_AGENT_TIER_NAME","value": applicationName}},
       {"op": "add","path": "/spec/template/spec/containers/0/env/-1","value": {"name": "APPDYNAMICS_AGENT_ACCOUNT_ACCESS_KEY","valueFrom": {"secretKeyRef": {"key": "access-key","name": "appd-agent-secret"}}}},
       {"op": "add","path": initContainer,"value": initContainerValue}
       ]
    
    # check if is a springboot application and append the java options
    if springBoot == "true":
        json_patch.append({"op": "add","path": "/spec/template/spec/containers/0/env/-1", "value": {"name": "JAVA_OPTS", "valueFrom": {"configMapKeyRef": {"name": "warden-java-opts-config", "key": "JAVA_OPTS"}}}})



    final_patch = json_patch + patch 

    final_patch = jsonpatch.JsonPatch(final_patch)
    
    #encode the patch and send the response to the api server
    base64_patch = base64.b64encode(final_patch.to_string().encode("utf-8")).decode("utf-8")
    return jsonify({"apiVersion": "admission.k8s.io/v1", "kind": "AdmissionReview", "response": {"allowed": True, "uid": uid, "status": {"message": message}, "patchType": "JSONPatch", "patch": base64_patch}})

if __name__ == '__main__':
    # warden.run(debug=True, host='0.0.0.0', port=5000)
     warden.run(ssl_context=('certs/tls.crt', 'certs/tls.key'),debug=True, host='0.0.0.0', port=5000)

