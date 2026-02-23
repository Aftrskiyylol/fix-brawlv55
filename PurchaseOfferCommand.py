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

            # Безопасное чтение с проверкой длины
            fields["OfferIndex"] = calling_instance.readVInt() if calling_instance.offset + 4 <= len(calling_instance.buffer) else 0
            fields["CurrencyType"] = calling_instance.readVInt() if calling_instance.offset + 4 <= len(calling_instance.buffer) else 0
            fields["ShopCategory"] = calling_instance.readDataReference() if calling_instance.offset + 8 <= len(calling_instance.buffer) else [0, 0]
            fields["ItemID"] = calling_instance.readDataReference() if calling_instance.offset + 8 <= len(calling_instance.buffer) else [0, 0]
            fields["Price"] = calling_instance.readVInt() if calling_instance.offset + 4 <= len(calling_instance.buffer) else 0
            fields["Unk6"] = calling_instance.readVInt() if calling_instance.offset + 4 <= len(calling_instance.buffer) else 0

            print(f"[DECODE] OfferIndex={fields['OfferIndex']}, Currency={fields['CurrencyType']}, "
                  f"Cat={fields['ShopCategory']}, Item={fields['ItemID']}, Price={fields['Price']}")

        except Exception as e:
            print(f"[DECODE ERROR] {e}")
            traceback.print_exc()
        return fields

    def execute(self, calling_instance, fields):
        try:
            player = calling_instance.player
            if not player:
                print("[ERROR] Player not found")
                self.send_home_data(calling_instance)
                return

            # Преобразуем объект в словарь
            player_dict = player.__dict__ if hasattr(player, '__dict__') else player

            offer_index = fields.get("OfferIndex", 0)
            currency_type = fields.get("CurrencyType", 0)
            shop_category = fields.get("ShopCategory", [0, 0])
            item_id = fields.get("ItemID", [0, 0])
            price = fields.get("Price", 0)

            player_name = player_dict.get('Name', 'Unknown')
            print(f"[PURCHASE] Player {player_name} buying cat={shop_category}, item={item_id}, price={price}, curr={currency_type}")

            # Если это не настоящая покупка (скин за 0 или левая валюта)
            if price <= 0 or currency_type not in [0, 1, 2]:
                print(f"[PURCHASE] Not a real purchase (price={price}, currency={currency_type})")
                self.send_home_data(calling_instance)
                return

            # Проверка валюты
            if currency_type == 0:
                current = player_dict.get("Gems", 0)
                if current < price:
                    print("[ERROR] Not enough Gems")
                    self.send_home_data(calling_instance)
                    return
                if hasattr(player, 'Gems'):
                    player.Gems = current - price
            elif currency_type == 1:
                current = player_dict.get("Coins", 0)
                if current < price:
                    print("[ERROR] Not enough Coins")
                    self.send_home_data(calling_instance)
                    return
                if hasattr(player, 'Coins'):
                    player.Coins = current - price
            elif currency_type == 2:
                current = player_dict.get("StarPoints", 0)
                if current < price:
                    print("[ERROR] Not enough StarPoints")
                    self.send_home_data(calling_instance)
                    return
                if hasattr(player, 'StarPoints'):
                    player.StarPoints = current - price

            # Выдача скина
            item_category = shop_category[0] if isinstance(shop_category, list) and len(shop_category) > 0 else 0
            if item_category == 16:
                brawler_id = item_id[0] if isinstance(item_id, list) and len(item_id) > 0 else 0
                skin_id = item_id[1] if isinstance(item_id, list) and len(item_id) > 1 else 0

                if brawler_id > 0 and skin_id > 0:
                    owned = player_dict.get("OwnedBrawlers", {})
                    key = str(brawler_id)
                    if key not in owned:
                        owned[key] = {"Skins": []}
                    if "Skins" not in owned[key]:
                        owned[key]["Skins"] = []
                    if skin_id not in owned[key]["Skins"]:
                        owned[key]["Skins"].append(skin_id)
                        print(f"[PURCHASE] Skin {skin_id} added for brawler {brawler_id}")

                    if hasattr(player, 'OwnedBrawlers'):
                        player.OwnedBrawlers = owned
                    elif hasattr(player, '__dict__'):
                        player.__dict__['OwnedBrawlers'] = owned

            # Сохраняем в БД
            self.save_player_data(calling_instance, player)

            # Отправляем home data (анимация!)
            self.send_home_data(calling_instance)
            print(f"[PURCHASE] Completed for {player_name}")

        except Exception as e:
            print(f"[EXECUTE ERROR] {e}")
            traceback.print_exc()
            self.send_home_data(calling_instance)

    def save_player_data(self, calling_instance, player):
        """Сохраняет данные игрока в БД"""
        try:
            # Пробуем получить доступ к БД
            db = None
            if hasattr(calling_instance, 'db'):
                db = calling_instance.db
            elif hasattr(calling_instance, 'player') and hasattr(calling_instance.player, 'db'):
                db = calling_instance.player.db

            if db:
                player_data = player.__dict__ if hasattr(player, '__dict__') else player
                cursor = db.cursor()
                cursor.execute("UPDATE main SET Data=? WHERE Token=?", 
                             (json.dumps(player_data), calling_instance.player_token))
                db.commit()
                print("[DB] Player data saved")
            else:
                print("[DB] No database connection")
        except Exception as e:
            print(f"[DB ERROR] {e}")

    def send_home_data(self, calling_instance):
        """Отправляет обновленные данные домой"""
        try:
            from Heart.Packets.Server.OwnHomeDataMessage import OwnHomeDataMessage
            
            msg = OwnHomeDataMessage(calling_instance)
            msg.encode()
            
            # Получаем буфер
            buffer = msg.buffer if hasattr(msg, 'buffer') else None
            
            if buffer and len(buffer) > 0:
                try:
                    Messaging.send(calling_instance, buffer)
                    print("[HOME] Sent HomeData")
                except Exception as e:
                    print(f"[HOME] Send failed: {e}")
            else:
                print("[HOME] No valid buffer")
        except Exception as e:
            print(f"[HOME ERROR] {e}")

    def getCommandType(self):
        return 519
