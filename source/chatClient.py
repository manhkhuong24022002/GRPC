import grpc
import threading
import chat_pb2 as chat_pb2
import chat_pb2_grpc as chat_pb2_grpc
from google.protobuf import empty_pb2 as google_dot_protobuf_dot_empty__pb2

def myHash(text:str):
    hash=0 
    for ch in text: 
        hash = ( hash*281 ^ ord(ch)*997) & 0xFFFFFFFF 
    return str(hash)

class ChatClient:
    def __init__(self, username, server_address='localhost', server_port=54321):
        self.username = username
        self.channel = grpc.insecure_channel(f'{server_address}:{server_port}')
        self.stub = chat_pb2_grpc.ChatServiceStub(self.channel)


    def register_user(self):
        request = chat_pb2.RegisterRequest(username=self.username)
        response = self.stub.RegisterUser(request)
        return response.success 
    
    def create_group_chat (self, group_id):
        request = chat_pb2.GroupRequest(group_id=group_id, username=self.username)
        response = self.stub.CreateGroup(request)
        return response.success
    
    def get_group_info_list(self):
        response = self.stub.GetGroupInfoList(google_dot_protobuf_dot_empty__pb2.Empty())
        for group_info in response.groups:
            members_list = [f"Username: {member}" for member in group_info.members]
            print(f"Group {group_info.group_id} members: {members_list}")

    def join_group(self, group_id):
        request = chat_pb2.JoinGroupRequest(username=self.username, group_id=group_id)
        response = self.stub.JoinGroup(request)
        return response.message
    
    def search_user_in_group(self,group_id_to_search, username_to_search):
        request = chat_pb2.SearchUserRequest(groupId_to_search=group_id_to_search,username_to_search=username_to_search)
        response = self.stub.SearchUserInGroup(request)
        return response.message
    
    def broadcast_message(self, group_id, content):
        request = chat_pb2.BroadcastMessageRequest(group_id=group_id, sender=self.username, content=content)
        response_stream = self.stub.BroadcastMessageStream(request)

        # Kiểm tra xem response_stream có tồn tại và không rỗng không
        if response_stream:
            for response in response_stream:
                print(f"Received broadcast: {response.message}")
        else:
            print("No response received from the server.")


    def get_group_chat(self, group_id):
        request = chat_pb2.GetGroupChatRequest(group_id=group_id)
        try:
            response = self.stub.GetGroupChat(request)
            if response.success:
                messages = response.messages
                for message in messages:
                    print(f"{message.index}              {message.sender}                 {message.content}")
            else:
                print(f"Failed to get group chat for group {group_id}: {response.message}")
        except grpc.RpcError as e:
            print(f"Error in RPC call: {e}")
        
    def send_private_message(self, receiver, content):
        request = chat_pb2.PrivateMessageRequest(sender=self.username, receiver=receiver, content= content)
        try:
            self.stub.SendPrivateMessage(request)
        except grpc.RpcError as e:
            print(f"Error in RPC call: {e}")

def client():
    while True:
        username = input("Enter your username to register: ")
        client = ChatClient(username)
        response = client.register_user()
        if response:
            print(f"Successfully registered username: {username}")
            break
        else:
            print("The username has already been registered. Please enter a different username to register.")
    while True:
        print("\nOptions:")
        print("1. Search User In A Group")
        print("2. Create Group Chat")
        print("3. Join Group")
        print("4. Send Group Chat Message")
        print("5. Send Private Chat Message")
        print("6. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            search_groupId = input("Enter group id to search: ")
            search_username = input("Enter username to search: ")
            result = client.search_user_in_group(search_groupId,search_username)
            print(result)
            
        elif choice == "2":
            groupId = input("Enter group id to create group chat: ")
            check = client.create_group_chat(groupId)
            if check:
                print("Successfully created a group chat")
                client.get_group_info_list()
            else:
                print("Creating a chat group failed due to the same chat group name")
           
        elif choice == "3":
            group_id = input("Enter group id to join: ")
            result = client.join_group(group_id)
            print(result)
            client.get_group_info_list()
            
            
        elif choice == "4":
            
            group_id = input("Enter the group ID to send a message: ")

            print(f"-----BOX CHAT GROUP {group_id}-----")
            client.get_group_chat(group_id)
            content = input("Enter a message to send: ")
            
            client.broadcast_message(group_id,content)

            print(f"-----BOX CHAT GROUP {group_id}-----")
            print("Index          Username          Content")
            client.get_group_chat(group_id)
           


        elif choice == "5":
            while True: 
                receiver = input("Enter username receiver: ")
                if receiver==username:
                    print("Sender and receiver names are the same, please enter again")
                else:
                    break
                
            result = client.send_private_message(receiver, "") #khoi tao id trong box group chat
            print(f"-----BOX CHAT TO USER: {receiver}-----")
            id = str(myHash(str(int(myHash(username)) + int(myHash(receiver)))))
            client.get_group_chat(id)
            
            content=input("Enter the content to send: ")
            result = client.send_private_message(receiver, content)
    
            print(f"-----BOX CHAT TO USER: {receiver}-----")
            print("Index          Username          Content")
            client.get_group_chat(id)
            print(result)


        elif choice == "6":
            break

        else:
            print("Invalid choice. Please try again.")
    
if __name__ == "__main__":
   client()