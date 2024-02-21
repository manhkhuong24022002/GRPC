import logging
import os
from glob import glob
import grpc
from concurrent import futures
import chat_pb2 as chat_pb2
import chat_pb2_grpc as chat_pb2_grpc
from google.protobuf.empty_pb2 import Empty
import time

log_file_list = glob("./server.log")

logging.root.setLevel(logging.NOTSET)
server_logger = logging.getLogger("__SERVER__LOG__")


# WRITE LOG
## OUTPUT CONSOLE
def get_output_console():
    output_console = logging.StreamHandler()
    output_console.setLevel(logging.INFO)
    output_foramt = logging.Formatter('%(name)s - %(levelname)s: \n%(message)s\n--------------------\n')
    output_console.setFormatter(output_foramt)
    return output_console


## OUT LOG FILE
def get_output_fileLog(path):
    out_file = logging.FileHandler(path)
    out_file.setLevel(logging.INFO)
    out_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s: \n%(message)s\n-----------\n')
    out_file.setFormatter(out_format)
    return out_file


def runlog(path):
    try:
        logger = logging.getLogger("__SERVER__LOG__")
        logger.addHandler(get_output_console())
        logger.addHandler(get_output_fileLog(path))
    except Exception as e:
        print(f"Error setting up logging: {e}")

def myHash(text:str):
    hash=0 
    for ch in text: 
        hash = ( hash*281 ^ ord(ch)*997) & 0xFFFFFFFF 
    return str(hash)

class ChatServer(chat_pb2_grpc.ChatServiceServicer):
    def __init__(self):
        self.users = {}  # Dùng để lưu thông tin của người dùng (username và địa chỉ)
        self.groups=[] # Dùng để lưu các group chat 
        self.box_chat_groups={} # Dùng để lưu các hộp thọai group chat
        self.connected_clients = {} # Dùng để lưu các client đang connected để server
        
    def RegisterUser(self, request, context):
        username = request.username
        if username in self.users:
            return chat_pb2.RegisterResponse(success=False)
        else:
            self.users[username] = {"username": username, "ip_address": context.peer()}
            response = chat_pb2.RegisterResponse(success=True)
            server_logger.info(f"User {username} registered from address {context.peer()}")
            return response

    def CreateGroup(self, request, context):
        group_id = request.group_id
        username = request.username

        # Kiểm tra xem nhóm đã tồn tại hay chưa
        existing_group = next((group for group in self.groups if group["group_id"] == group_id), None)

        if existing_group is None:
            # Nếu nhóm chưa tồn tại, tạo mới một từ điển nhóm và thêm vào danh sách
            new_group = {"group_id": group_id, "members": [{"username": username, "ip_address": context.peer()}]}
            self.groups.append(new_group)
            server_logger.info(f"User {username} successfully created group chat {group_id}")
            return chat_pb2.GroupResponse(success=True)
        else:
            server_logger.info(f"User {username} created a group chat {group_id} that failed")
            return chat_pb2.GroupResponse(success=False)

    def GetGroupInfoList(self, request, context):
            group_info_list = []
            for group in self.groups:
                members_list = [f"Username: {member['username']} ({member['ip_address']})" for member in group["members"]]
                group_info = chat_pb2.GroupInfo(group_id=group["group_id"], members=members_list)
                group_info_list.append(group_info)
                server_logger.info(f"Group {group['group_id']} members: {members_list}")

            server_logger.info(f"Group info list: {group_info_list}")
            # Không cần trả về thông tin cho client, chỉ cần in ra console
            return Empty()
    
    def JoinGroup(self, request, context):
        username = request.username
        group_id = request.group_id

        # Kiểm tra xem nhóm có tồn tại không
        existing_group = next((group for group in self.groups if group["group_id"] == group_id), None)

        if existing_group:
            # Kiểm tra xem username đã tham gia nhóm chưa
            if username not in [member["username"] for member in existing_group["members"]]:
                existing_group["members"].append({"username": username, "ip_address": context.peer()})
                response = chat_pb2.JoinGroupResponse( message=f"User {username} joined the group {group_id}")
                server_logger.info(f"User {username} joined the group {group_id}")

            else:
                response = chat_pb2.JoinGroupResponse(message=f"User {username} is already in the group {group_id}")
                server_logger.info(f"User {username} is already in the group {group_id}")
        else:
            response = chat_pb2.JoinGroupResponse(message=f"Group {group_id} does not exist")
            server_logger.info(f"User {username} failed to join group  {group_id} because group  {group_id} does not exist")

        return response
    
    def SearchUserInGroup (self, request, context):
        group_id_to_search = request.groupId_to_search
        username_to_search = request.username_to_search
    
        existing_group = next((group for group in self.groups if group["group_id"] == group_id_to_search), None)
        if existing_group:
            user_exists = any(member["username"] == username_to_search for member in existing_group["members"])
            if user_exists:
                response = chat_pb2.SearchUserResponse( message=f"User {username_to_search} is in the group" )
                server_logger.info(f"User {username_to_search} is in the group.")
                
            else:
                response = chat_pb2.SearchUserResponse(message=f"User {username_to_search} is not in the group.")
                server_logger.info(f"User {username_to_search} is not in the group.")

        else:
            response = chat_pb2.SearchUserResponse(message=f"Group {group_id_to_search} does not exist.")
            server_logger.info(f"Group {group_id_to_search} does not exist.")
            
        return response
             
    def BroadcastMessageStream(self, request, context):
        group_id = request.group_id
        sender = request.sender
        content = request.content

        # Kiểm tra xem group_id có tồn tại không
        if group_id not in [group['group_id'] for group in self.groups]:
            server_logger.info(f"User {sender} sends a broadcast messagefailed to go to group chat {group_id} because group chat {group_id} does not exist")
            yield chat_pb2.BroadcastMessageResponse(success=False, message=f"Group {group_id} does not exist")
            return
        
        # Lưu thông điệp vào box_chat_groups
        if group_id not in self.box_chat_groups:
            self.box_chat_groups[group_id] = {"messages": [], "members": []}

        # Lấy vị trí index gửi (số thứ tự trong danh sách tin nhắn của nhóm)
        index = len(self.box_chat_groups[group_id]["messages"]) + 1

        # Lưu thông điệp vào danh sách tin nhắn của nhóm
        message = {"index": index, "sender": sender, "content": content}
        self.box_chat_groups[group_id]["messages"].append(message)

        # Lấy danh sách thành viên trong nhóm
        group_members = self.connected_clients.get(group_id, {}).items()

        # Lưu danh sách thành viên vào box_chat_groups
        self.box_chat_groups[group_id]["members"] = [member_username for member_username, _ in group_members]

        for member_username, member_channel in group_members:
            if member_username != sender:
                response = chat_pb2.BroadcastMessageResponse(success=True, message=f"{sender}: {content}")

                # Kiểm tra điều kiện trước khi gửi dữ liệu đến từng thành viên trong nhóm
                if member_channel is not None:
                    member_channel.SendMessage(response)
                else:
                    # Xử lý lỗi khi thành viên trong nhóm không có kênh
                    server_logger.info(f"Error: User {member_username} does not have a valid channel")

        server_logger.info(f"User {sender} send the broadcast message successfully to group chat {group_id}")
        # Trả về phản hồi cho client gửi tin nhắn
        
        yield chat_pb2.BroadcastMessageResponse(success=True, message="Message broadcasted successfully")

    def GetGroupChat(self, request, context):
        group_id = request.group_id

        # Kiểm tra xem nhóm có tồn tại không
        if group_id in self.box_chat_groups:
            # Trả về danh sách tin nhắn của nhóm
            messages = self.box_chat_groups[group_id]["messages"]
            response = chat_pb2.GetGroupChatResponse(success=True, messages=messages)
        else:
            response = chat_pb2.GetGroupChatResponse(success=False, message=f"Group {group_id} does not exist")

        return response
    
    def SendPrivateMessage(self, request : chat_pb2.PrivateMessageRequest, context):
        sender = request.sender
        receiver = request.receiver
        content =  request.content

        id = str(myHash(str(int(myHash(sender)) + int(myHash(receiver)))))
        list_id =  list(self.box_chat_groups.keys())
        if id not in list_id and content=="":
            self.box_chat_groups[id] = {"messages": [], "members": []}
        if content != "":
            index = len(self.box_chat_groups[id]["messages"]) + 1
            message = {"index": index, "sender": sender, "content": content}
            self.box_chat_groups[id]["messages"].append(message)
        server_logger.info(f"User {sender} has successfully sent a message to user {receiver}.")
        return chat_pb2.Empty()
    
def serve():
    for file in log_file_list:
        os.remove(file)
    runlog("server.log")
    port=54321
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=30))
    chat_pb2_grpc.add_ChatServiceServicer_to_server(ChatServer(), server)
    server.add_insecure_port('[::]:'+str(port))
    server.start()
    server_logger.info("Server is running...")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()

