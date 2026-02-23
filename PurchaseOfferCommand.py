from Heart.Commands.LogicCommand import LogicCommand
from Heart.Messaging import Messaging
import json
import traceback

class PurchaseOfferCommand(LogicCommand):
    def __init__(self, commandData):
        super().__init__(commandData)

    def encode(self, fields):
        try:
            LogicCommand.encode(self, fields)
            self.writeVInt(1)  # 1 = успех
            self.writeDataReference(0)
            self.writeVInt(0)
        except Exception as e:
            print(f"[ENCODE ERROR] {e}")
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
            
            LogicCommand.parseFields(fields)
            
            print(f"[DECODE] OfferIndex: {fields['OfferIndex']}")
            print(f"[DECODE] ShopCategory: {fields['ShopCategory']}")
            print(f"[DECODE] ItemID: {fields['ItemID']}")
            print(f"[DECODE] CurrencyType: {fields['CurrencyType']}")
            print(f"[DECODE] Price: {fields['Price']}")
            
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
        purchase_success = False
        
        try:
            player = calling_instance.player
            if not player:
                print("[ERROR] Player not found")
                self.safe_send_home(calling_instance)
                return

            player_dict = self.player_to_dict(player)
            
            offer_index = fields.get("OfferIndex", 0)
            shop_category = fields.get("ShopCategory", [0, 0])
            item_id = fields.get("ItemID", [0, 0])
            currency_type = fields.get("CurrencyType", 0)
            price = fields.get("Price", 0)
            
            # Безопасное извлечение категории и ID
            item_category = 0
            if isinstance(shop_category, list) and len(shop_category) >= 2:
                item_category = shop_category[0]
            
            brawler_id = 0
            skin_id = 0
            if isinstance(item_id, list) and len(item_id) >= 2:
                brawler_id = item_id[0]
                skin_id = item_id[1]
            
            player_name = player_dict.get('Name', 'Unknown')
            print(f"[PURCHASE] Player: {player_name}")
            print(f"[PURCHASE] Category: {item_category}, Item: ({brawler_id},{skin_id})")
            print(f"[PURCHASE] Price: {price}, Currency: {currency_type}")
            
            # Если нет цены или предмета - просто выходим
            if price <= 0 or (item_category == 0 and brawler_id == 0):
                print(f"[PURCHASE] Nothing to buy")
                self.safe_send_home(calling_instance)
                return
            
            # Проверка баланса и списание
            if currency_type == 0:  # Гемы
                current = player_dict.get("Gems", 0)
                if current >= price:
                    self.safe_set_attr(player, "Gems", current - price)
                    print(f"[PURCHASE] New gems: {current - price}")
                    purchase_success = True
                else:
                    print(f"[ERROR] Not enough gems")
                    
            elif currency_type == 1:  # Монеты
                current = player_dict.get("Coins", 0)
                if current >= price:
                    self.safe_set_attr(player, "Coins", current - price)
                    print(f"[PURCHASE] New coins: {current - price}")
                    purchase_success = True
                else:
                    print(f"[ERROR] Not enough coins")
                    
            elif currency_type == 2:  # Звездные очки
                current = player_dict.get("StarPoints", 0)
                if current >= price:
                    self.safe_set_attr(player, "StarPoints", current - price)
                    print(f"[PURCHASE] New starpoints: {current - price}")
                    purchase_success = True
                else:
                    print(f"[ERROR] Not enough starpoints")
            
            # Выдача скина
            if purchase_success and item_category == 16 and brawler_id > 0 and skin_id > 0:
                owned_brawlers = self.safe_get_owned_brawlers(player)
                brawler_key = str(brawler_id)
                
                if brawler_key in owned_brawlers:
                    brawler_data = owned_brawlers[brawler_key]
                    if "Skins" not in brawler_data:
                        brawler_data["Skins"] = []
                    if skin_id not in brawler_data["Skins"]:
                        brawler_data["Skins"].append(skin_id)
                        self.safe_set_owned_brawlers(player, owned_brawlers)
                        print(f"[PURCHASE] Skin {skin_id} added")
                        self.safe_save_player(calling_instance, player)
            
        except Exception as e:
            print(f"[EXECUTE ERROR] {e}")
            traceback.print_exc()
        
        # ВСЕГДА отправляем home data
        self.safe_send_home(calling_instance)

    # ========== БЕЗОПАСНЫЕ ФУНКЦИИ ==========

    def safe_send_home(self, calling_instance):
        """Абсолютно безопасная отправка home data"""
        try:
            from Heart.Packets.Server.OwnHomeDataMessage import OwnHomeDataMessage
            
            home_msg = OwnHomeDataMessage(calling_instance)
            home_msg.encode()
            
            # Проверяем, что buffer существует
            if hasattr(home_msg, 'buffer') and home_msg.buffer is not None:
                # Пробуем разные способы отправки
                try:
                    # Способ 1: через Messaging
                    Messaging.send(calling_instance, home_msg.buffer)
                    print("[HOME] Sent via Messaging")
                except:
                    try:
                        # Способ 2: прямой send
                        calling_instance.send(home_msg.buffer)
                        print("[HOME] Sent via direct send")
                    except:
                        print("[HOME] Could not send, but no crash")
            else:
                print("[HOME] No buffer to send")
                
        except Exception as e:
            print(f"[HOME SAFE ERROR] {e}")

    def safe_set_attr(self, obj, attr, value):
        """Безопасно устанавливает атрибут"""
        try:
            if hasattr(obj, attr):
                setattr(obj, attr, value)
            elif isinstance(obj, dict):
                obj[attr] = value
            elif hasattr(obj, '__dict__'):
                obj.__dict__[attr] = value
        except:
            pass

    def safe_get_owned_brawlers(self, player):
        """Безопасно получает OwnedBrawlers"""
        try:
            if hasattr(player, 'OwnedBrawlers'):
                return player.OwnedBrawlers
            elif isinstance(player, dict) and 'OwnedBrawlers' in player:
                return player['OwnedBrawlers']
            elif hasattr(player, '__dict__') and 'OwnedBrawlers' in player.__dict__:
                return player.__dict__['OwnedBrawlers']
        except:
            pass
        return {}

    def safe_set_owned_brawlers(self, player, brawlers):
        """Безопасно устанавливает OwnedBrawlers"""
        try:
            if hasattr(player, 'OwnedBrawlers'):
                player.OwnedBrawlers = brawlers
            elif isinstance(player, dict):
                player['OwnedBrawlers'] = brawlers
            elif hasattr(player, '__dict__'):
                player.__dict__['OwnedBrawlers'] = brawlers
        except:
            pass

    def safe_save_player(self, calling_instance, player):
        """Безопасно сохраняет игрока в БД"""
        try:
            if hasattr(calling_instance, 'db') and calling_instance.db:
                # Преобразуем в JSON
                if hasattr(player, '__dict__'):
                    player_json = json.dumps(player.__dict__)
                elif isinstance(player, dict):
                    player_json = json.dumps(player)
                else:
                    player_json = json.dumps({})
                
                cursor = calling_instance.db.cursor()
                cursor.execute(
                    "UPDATE main SET Data = ? WHERE Token = ?",
                    (player_json, calling_instance.player_token)
                )
                calling_instance.db.commit()
                print("[DB] Saved")
        except Exception as e:
            print(f"[DB ERROR] {e}")

    def player_to_dict(self, player):
        """Преобразует игрока в словарь"""
        try:
            if hasattr(player, '__dict__'):
                return player.__dict__
            elif isinstance(player, dict):
                return player
        except:
            pass
        return {}

    def getCommandType(self):
        return 519
