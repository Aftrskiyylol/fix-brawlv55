from Heart.Commands.LogicCommand import LogicCommand
from Heart.Messaging import Messaging
import json
import time
import traceback

class PurchaseOfferCommand(LogicCommand):
    def __init__(self, commandData):
        super().__init__(commandData)

    def encode(self, fields):
        try:
            LogicCommand.encode(self, fields)
            # Отправляем подтверждение успешной покупки
            self.writeVInt(1)  # 1 = успех, 0 = ошибка
            self.writeDataReference(0)
            self.writeVInt(0)
        except Exception as e:
            print(f"[ENCODE ERROR] {e}")
        return self.messagePayload

    def decode(self, calling_instance):
        fields = {}
        try:
            LogicCommand.decode(calling_instance, fields, False)
            
            # Безопасное чтение с защитой от выхода за границы
            fields["OfferIndex"] = self.safe_read_vint(calling_instance, 0)
            fields["ShopCategory"] = self.safe_read_dataref(calling_instance, [0, 0])
            fields["ItemID"] = self.safe_read_dataref(calling_instance, [0, 0])
            fields["CurrencyType"] = self.safe_read_vint(calling_instance, 0)
            fields["Price"] = self.safe_read_vint(calling_instance, 0)
            fields["Unk6"] = self.safe_read_vint(calling_instance, 0)
            
            LogicCommand.parseFields(fields)
        except Exception as e:
            print(f"[DECODE ERROR] {e}")
            traceback.print_exc()
        return fields

    def safe_read_vint(self, caller, default=0):
        """Безопасное чтение VInt с защитой от IndexError"""
        try:
            if caller.offset < len(caller.buffer):
                return caller.readVInt()
        except:
            pass
        return default

    def safe_read_dataref(self, caller, default=[0, 0]):
        """Безопасное чтение DataReference"""
        try:
            if caller.offset + 8 <= len(caller.buffer):
                return caller.readDataReference()
        except:
            pass
        return default

    def execute(self, calling_instance, fields):
        try:
            # Получаем игрока
            player = calling_instance.player
            if not player:
                print("[ERROR] Player not found")
                return
            
            # Извлекаем данные с защитой
            offer_index = fields.get("OfferIndex", 0)
            shop_category = fields.get("ShopCategory", [0, 0])
            item_id = fields.get("ItemID", [0, 0])
            currency_type = fields.get("CurrencyType", 0)
            price = fields.get("Price", 0)
            
            # Приводим к нормальному виду
            if isinstance(shop_category, list) and len(shop_category) >= 2:
                item_category = shop_category[0]
            else:
                item_category = 0
                print(f"[WARN] Invalid shop_category: {shop_category}")
            
            if isinstance(item_id, list) and len(item_id) >= 2:
                brawler_id = item_id[0]
                skin_id = item_id[1]
            else:
                brawler_id = 0
                skin_id = 0
                print(f"[WARN] Invalid item_id: {item_id}")
            
            # Логируем
            player_name = player.get('Name', 'Unknown')
            print(f"[PURCHASE] {player_name} buying: cat={item_category}, item=({brawler_id},{skin_id}), price={price}, curr={currency_type}")
            
            # Проверка цены
            if price <= 0:
                print(f"[WARN] Price is {price}, skipping")
                return
            
            # Проверка баланса
            if currency_type == 0:  # Гемы
                if player.get("Gems", 0) < price:
                    print(f"[ERROR] Not enough gems: has {player.get('Gems', 0)}, needs {price}")
                    return
                player["Gems"] = player.get("Gems", 0) - price
                print(f"[PURCHASE] New gems balance: {player['Gems']}")
                
            elif currency_type == 1:  # Монеты
                if player.get("Coins", 0) < price:
                    print(f"[ERROR] Not enough coins: has {player.get('Coins', 0)}, needs {price}")
                    return
                player["Coins"] = player.get("Coins", 0) - price
                print(f"[PURCHASE] New coins balance: {player['Coins']}")
                
            elif currency_type == 2:  # Звездные очки
                if player.get("StarPoints", 0) < price:
                    print(f"[ERROR] Not enough starpoints: has {player.get('StarPoints', 0)}, needs {price}")
                    return
                player["StarPoints"] = player.get("StarPoints", 0) - price
                print(f"[PURCHASE] New starpoints: {player['StarPoints']}")
            
            # Выдача предмета (скины)
            if item_category == 16 and brawler_id > 0 and skin_id > 0:
                brawler_key = str(brawler_id)
                if brawler_key in player.get("OwnedBrawlers", {}):
                    if "Skins" not in player["OwnedBrawlers"][brawler_key]:
                        player["OwnedBrawlers"][brawler_key]["Skins"] = []
                    if skin_id not in player["OwnedBrawlers"][brawler_key]["Skins"]:
                        player["OwnedBrawlers"][brawler_key]["Skins"].append(skin_id)
                        print(f"[PURCHASE] Skin {skin_id} for brawler {brawler_id} added")
                else:
                    print(f"[WARN] Brawler {brawler_id} not owned by player")
            
            # Сохраняем в БД
            self.save_player_data(calling_instance, player)
            
            # Отправляем обновление клиенту
            self.send_home_data(calling_instance)
            
            print(f"[PURCHASE] ✅ Success for {player_name}")
            
        except Exception as e:
            print(f"[EXECUTE ERROR] {e}")
            traceback.print_exc()

    def save_player_data(self, calling_instance, player_data):
        """Сохраняет данные игрока в БД"""
        try:
            if hasattr(calling_instance, 'db') and calling_instance.db:
                cursor = calling_instance.db.cursor()
                cursor.execute(
                    "UPDATE main SET Data = ? WHERE Token = ?",
                    (json.dumps(player_data), calling_instance.player_token)
                )
                calling_instance.db.commit()
                print("[DB] Player data saved")
        except Exception as e:
            print(f"[DB ERROR] {e}")

    def send_home_data(self, calling_instance):
        """Отправляет обновленные данные домой"""
        try:
            from Heart.Packets.Server.OwnHomeDataMessage import OwnHomeDataMessage
            home_msg = OwnHomeDataMessage(calling_instance)
            home_msg.encode()
            Messaging.send(calling_instance, home_msg.buffer)
            print("[HOME] Home data sent to client")
        except Exception as e:
            print(f"[HOME ERROR] {e}")

    def getCommandType(self):
        return 519
