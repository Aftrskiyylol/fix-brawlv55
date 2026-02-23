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
        buffer = getattr(calling_instance, 'buffer', None) or getattr(calling_instance, 'messagePayload', None) or getattr(calling_instance, 'payload', None)
        if not buffer:
            print(f"[DECODE SKIP] Not a valid message: {type(calling_instance)}")
            return fields

        try:
            LogicCommand.decode(calling_instance, fields, False)
        except Exception:
            pass

        # 🔹 Безопасное чтение всех полей
        def safe_read(reader, default):
            try:
                return reader()
            except Exception:
                return default

        fields["OfferIndex"] = safe_read(calling_instance.readVInt, 0)
        fields["CurrencyType"] = safe_read(calling_instance.readVInt, 0)
        fields["ShopCategory"] = safe_read(calling_instance.readDataReference, [0, 0])
        fields["ItemID"] = safe_read(calling_instance.readDataReference, [0, 0])
        fields["Price"] = safe_read(calling_instance.readVInt, 0)
        fields["Unk6"] = safe_read(calling_instance.readVInt, 0)

        # Ограничение валидных значений
        if fields["OfferIndex"] < 0 or fields["OfferIndex"] > 10000:
            fields["OfferIndex"] = 0
        if fields["CurrencyType"] not in [0, 1, 2]:
            fields["CurrencyType"] = 0
        if not isinstance(fields["ShopCategory"], list) or len(fields["ShopCategory"]) != 2:
            fields["ShopCategory"] = [0, 0]
        if not isinstance(fields["ItemID"], list) or len(fields["ItemID"]) != 2:
            fields["ItemID"] = [0, 0]
        if fields["Price"] < 0:
            fields["Price"] = 0

        print(f"[DECODE] OfferIndex={fields['OfferIndex']}, Currency={fields['CurrencyType']}, "
              f"Cat={fields['ShopCategory']}, Item={fields['ItemID']}, Price={fields['Price']}")
        return fields

    def execute(self, calling_instance, fields):
        try:
            player = getattr(calling_instance, 'player', None)
            if not player:
                print("[ERROR] Player not found")
                self.send_home_data(calling_instance)
                return

            player_dict = player.__dict__ if hasattr(player, '__dict__') else player
            offer_index = fields.get("OfferIndex", 0)
            currency_type = fields.get("CurrencyType", 0)
            shop_category = fields.get("ShopCategory", [0, 0])
            item_id = fields.get("ItemID", [0, 0])
            price = fields.get("Price", 0)

            player_name = player_dict.get('Name', 'Unknown')
            print(f"[PURCHASE] Player {player_name} buying cat={shop_category}, item={item_id}, price={price}, curr={currency_type}")

            if price <= 0:
                print(f"[PURCHASE] Not a real purchase (price={price}, currency={currency_type})")
                self.send_home_data(calling_instance)
                return

            # 🔹 Снимаем валюту
            if currency_type == 0:
                current = player_dict.get("Gems", 0)
                if current < price:
                    self.send_home_data(calling_instance)
                    return
                player.Gems = current - price
            elif currency_type == 1:
                current = player_dict.get("Coins", 0)
                if current < price:
                    self.send_home_data(calling_instance)
                    return
                player.Coins = current - price
            elif currency_type == 2:
                current = player_dict.get("StarPoints", 0)
                if current < price:
                    self.send_home_data(calling_instance)
                    return
                player.StarPoints = current - price

            # 🔹 Выдача скина
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
                    player.OwnedBrawlers = owned

            # 🔹 Сохраняем данные и отправляем HomeData
            self.save_player_data(calling_instance, player)
            self.send_home_data(calling_instance)
            print(f"[PURCHASE] Completed for {player_name}")

        except Exception as e:
            print(f"[EXECUTE ERROR] {e}")
            traceback.print_exc()
            self.send_home_data(calling_instance)

    def save_player_data(self, calling_instance, player):
        try:
            db = getattr(calling_instance, 'db', None) or getattr(getattr(calling_instance, 'player', None), 'db', None)
            if db:
                player_data = player.__dict__ if hasattr(player, '__dict__') else player
                cursor = db.cursor()
                cursor.execute("UPDATE main SET Data=? WHERE Token=?", (json.dumps(player_data), getattr(calling_instance, 'player_token', '')))
                db.commit()
                print("[DB] Player data saved")
        except Exception as e:
            print(f"[DB ERROR] {e}")

    def send_home_data(self, calling_instance):
        try:
            from Heart.Packets.Server.OwnHomeDataMessage import OwnHomeDataMessage
            msg = OwnHomeDataMessage(calling_instance)
            msg.encode()
            buffer = getattr(msg, 'buffer', None) or getattr(msg, 'payload', None) or getattr(msg, 'data', None)

            if buffer:
                if hasattr(calling_instance, 'send') and callable(calling_instance.send):
                    calling_instance.send(buffer)
                    print("[HOME] Sent HomeData via direct send()")
                else:
                    try:
                        Messaging.send(calling_instance, buffer)
                        print("[HOME] Sent HomeData via Messaging")
                    except Exception as e:
                        print(f"[HOME ERROR] Messaging send failed: {e}")
            else:
                print("[HOME] No buffer to send")
        except Exception as e:
            print(f"[HOME ERROR] {e}")

    def getCommandType(self):
        return 519
