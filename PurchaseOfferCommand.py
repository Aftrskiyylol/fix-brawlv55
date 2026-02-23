from Heart.Commands.LogicCommand import LogicCommand
from Heart.Messaging import Messaging
import json
import traceback

class PurchaseOfferCommand(LogicCommand):
    def __init__(self, commandData):
        super().__init__(commandData)

    def encode(self, fields):
        LogicCommand.encode(self, fields)
        self.writeVInt(1)
        self.writeDataReference(0)
        self.writeVInt(0)
        return self.messagePayload

    def decode(self, calling_instance):
        fields = {}
        try:
            LogicCommand.decode(calling_instance, fields, False)
            fields["OfferIndex"] = self.safe_read_vint(calling_instance, 0)
            fields["ShopCategory"] = self.safe_read_dataref(calling_instance, [0, 0])
            fields["ItemID"] = self.safe_read_dataref(calling_instance, [0, 0])
            fields["CurrencyType"] = self.safe_read_vint(calling_instance, 0)
            fields["Price"] = self.safe_read_vint(calling_instance, 0)
            fields["Unk6"] = self.safe_read_vint(calling_instance, 0)
        except Exception as e:
            print(f"[DECODE ERROR] {e}")
            traceback.print_exc()
        return fields

    def safe_read_vint(self, caller, default=0):
        try:
            if hasattr(caller, 'offset') and hasattr(caller, 'buffer'):
                if caller.offset < len(caller.buffer):
                    return caller.readVInt()
        except:
            pass
        return default

    def safe_read_dataref(self, caller, default=[0, 0]):
        try:
            if hasattr(caller, 'offset') and hasattr(caller, 'buffer'):
                if caller.offset + 8 <= len(caller.buffer):
                    return caller.readDataReference()
        except:
            pass
        return default

    def execute(self, calling_instance, fields):
        try:
            player = calling_instance.player
            if not player:
                print("[ERROR] Player not found")
                self.send_home_data(calling_instance)
                return

            # Преобразуем объект в словарь если нужно
            if hasattr(player, '__dict__'):
                player_dict = player.__dict__
            else:
                player_dict = player

            offer_index = fields.get("OfferIndex", 0)
            shop_category = fields.get("ShopCategory", [0, 0])
            item_id = fields.get("ItemID", [0, 0])
            currency_type = fields.get("CurrencyType", 0)
            price = fields.get("Price", 0)

            player_name = player_dict.get('Name', 'Unknown')
            print(f"[PURCHASE] Player {player_name} buying cat={shop_category}, item={item_id}, price={price}, curr={currency_type}")

            # Проверка валюты через словарь
            if currency_type == 0:
                if player_dict.get("Gems", 0) < price:
                    print("[ERROR] Not enough Gems")
                    self.send_home_data(calling_instance)
                    return
                # Устанавливаем через объект
                if hasattr(player, 'Gems'):
                    player.Gems = player_dict.get("Gems", 0) - price
            elif currency_type == 1:
                if player_dict.get("Coins", 0) < price:
                    print("[ERROR] Not enough Coins")
                    self.send_home_data(calling_instance)
                    return
                if hasattr(player, 'Coins'):
                    player.Coins = player_dict.get("Coins", 0) - price
            elif currency_type == 2:
                if player_dict.get("StarPoints", 0) < price:
                    print("[ERROR] Not enough StarPoints")
                    self.send_home_data(calling_instance)
                    return
                if hasattr(player, 'StarPoints'):
                    player.StarPoints = player_dict.get("StarPoints", 0) - price

            # Выдача скина
            item_category = shop_category[0] if isinstance(shop_category, list) else 0
            if item_category == 16:
                brawler_id = item_id[0] if isinstance(item_id, list) else 0
                skin_id = item_id[1] if isinstance(item_id, list) and len(item_id) > 1 else 0

                owned = player_dict.get("OwnedBrawlers", {})
                key = str(brawler_id)
                if key not in owned:
                    owned[key] = {"Skins":[]}

                if "Skins" not in owned[key]:
                    owned[key]["Skins"] = []

                if skin_id not in owned[key]["Skins"]:
                    owned[key]["Skins"].append(skin_id)
                    print(f"[PURCHASE] Skin {skin_id} added for brawler {brawler_id}")

                # Сохраняем обратно в объект
                if hasattr(player, 'OwnedBrawlers'):
                    player.OwnedBrawlers = owned
                elif hasattr(player, '__dict__'):
                    player.__dict__['OwnedBrawlers'] = owned

            # Сохраняем
            self.save_player_data(calling_instance, player)

            # Отправляем home data (анимация!)
            self.send_home_data(calling_instance)
            print(f"[PURCHASE] Completed for {player_name}")

        except Exception as e:
            print(f"[EXECUTE ERROR] {e}")
            traceback.print_exc()
            self.send_home_data(calling_instance)

    def save_player_data(self, calling_instance, player):
        try:
            if hasattr(player, '__dict__'):
                player_data = player.__dict__
            else:
                player_data = player

            cursor = calling_instance.db.cursor()
            cursor.execute("UPDATE main SET Data=? WHERE Token=?", (json.dumps(player_data), calling_instance.player_token))
            calling_instance.db.commit()
            print("[DB] Player data saved")
        except Exception as e:
            print(f"[DB ERROR] {e}")

    def send_home_data(self, calling_instance):
        try:
            from Heart.Packets.Server.OwnHomeDataMessage import OwnHomeDataMessage
            msg = OwnHomeDataMessage(calling_instance)
            msg.encode()
            if hasattr(msg, 'buffer') and msg.buffer:
                Messaging.send(calling_instance, msg.buffer)
                print("[HOME] Sent HomeData")
            else:
                print("[HOME] No buffer")
        except Exception as e:
            print(f"[HOME ERROR] {e}")

    def getCommandType(self):
        return 519
