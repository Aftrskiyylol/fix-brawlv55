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
            # 1 = успех, 0 = ошибка
            self.writeVInt(1)
            self.writeDataReference(0)
            self.writeVInt(0)
        except Exception as e:
            print(f"[ENCODE ERROR] {e}")
        return self.messagePayload

    def decode(self, calling_instance):
        fields = {}
        try:
            LogicCommand.decode(calling_instance, fields, False)
            
            # Безопасное чтение всех полей
            fields["OfferIndex"] = self.safe_read_vint(calling_instance, 0)
            fields["ShopCategory"] = self.safe_read_dataref(calling_instance, [0, 0])
            fields["ItemID"] = self.safe_read_dataref(calling_instance, [0, 0])
            fields["CurrencyType"] = self.safe_read_vint(calling_instance, 0)
            fields["Price"] = self.safe_read_vint(calling_instance, 0)
            fields["Unk6"] = self.safe_read_vint(calling_instance, 0)
            
            LogicCommand.parseFields(fields)
            
            # Логируем полученные данные
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
        """Безопасное чтение VInt с защитой от IndexError"""
        try:
            if hasattr(caller, 'offset') and hasattr(caller, 'buffer'):
                if caller.offset < len(caller.buffer):
                    return caller.readVInt()
        except:
            pass
        return default

    def safe_read_dataref(self, caller, default=[0, 0]):
        """Безопасное чтение DataReference"""
        try:
            if hasattr(caller, 'offset') and hasattr(caller, 'buffer'):
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

            # Преобразуем игрока в словарь для удобства
            player_dict = self.player_to_dict(player)
            
            # Извлекаем данные с защитой
            offer_index = fields.get("OfferIndex", 0)
            shop_category = fields.get("ShopCategory", [0, 0])
            item_id = fields.get("ItemID", [0, 0])
            currency_type = fields.get("CurrencyType", 0)
            price = fields.get("Price", 0)
            
            # Приводим к нормальному виду
            if isinstance(shop_category, list) and len(shop_category) >= 2:
                item_category = shop_category[0]
                item_sub = shop_category[1]
            else:
                item_category = 0
                item_sub = 0
                print(f"[WARN] Invalid shop_category: {shop_category}")
            
            if isinstance(item_id, list) and len(item_id) >= 2:
                brawler_id = item_id[0]
                skin_id = item_id[1]
            else:
                brawler_id = 0
                skin_id = 0
                print(f"[WARN] Invalid item_id: {item_id}")
            
            # Логируем
            player_name = player_dict.get('Name', 'Unknown')
            print(f"[PURCHASE] Player: {player_name}")
            print(f"[PURCHASE] Category: {item_category}, Item: ({brawler_id},{skin_id})")
            print(f"[PURCHASE] Price: {price}, Currency: {currency_type}")
            
            # Если цена 0 или нет предмета — ничего не делаем
            if price <= 0 or (item_category == 0 and brawler_id == 0):
                print(f"[PURCHASE] Nothing to buy (price=0 or invalid item)")
                return
            
            # Проверка баланса
            if currency_type == 0:  # Гемы
                current = player_dict.get("Gems", 0)
                if current < price:
                    print(f"[ERROR] Not enough gems: has {current}, needs {price}")
                    return
                # Обновляем через setattr (так как player — объект)
                setattr(player, "Gems", current - price)
                print(f"[PURCHASE] New gems balance: {current - price}")
                
            elif currency_type == 1:  # Монеты
                current = player_dict.get("Coins", 0)
                if current < price:
                    print(f"[ERROR] Not enough coins: has {current}, needs {price}")
                    return
                setattr(player, "Coins", current - price)
                print(f"[PURCHASE] New coins balance: {current - price}")
                
            elif currency_type == 2:  # Звездные очки
                current = player_dict.get("StarPoints", 0)
                if current < price:
                    print(f"[ERROR] Not enough starpoints: has {current}, needs {price}")
                    return
                setattr(player, "StarPoints", current - price)
                print(f"[PURCHASE] New starpoints: {current - price}")
            
            # Выдача предмета (скины)
            if item_category == 16 and brawler_id > 0 and skin_id > 0:
                # Получаем OwnedBrawlers (это может быть атрибут или ключ в словаре)
                owned_brawlers = self.get_owned_brawlers(player)
                
                if owned_brawlers and str(brawler_id) in owned_brawlers:
                    brawler_data = owned_brawlers[str(brawler_id)]
                    
                    if "Skins" not in brawler_data:
                        brawler_data["Skins"] = []
                    
                    if skin_id not in brawler_data["Skins"]:
                        brawler_data["Skins"].append(skin_id)
                        self.set_owned_brawlers(player, owned_brawlers)
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

    def player_to_dict(self, player):
        """Преобразует объект Player в словарь"""
        try:
            if hasattr(player, '__dict__'):
                return player.__dict__
            elif isinstance(player, dict):
                return player
            else:
                return {}
        except:
            return {}

    def get_owned_brawlers(self, player):
        """Безопасно получает OwnedBrawlers"""
        try:
            if hasattr(player, 'OwnedBrawlers'):
                return player.OwnedBrawlers
            elif isinstance(player, dict) and 'OwnedBrawlers' in player:
                return player['OwnedBrawlers']
            else:
                # Пробуем найти в __dict__
                if hasattr(player, '__dict__') and 'OwnedBrawlers' in player.__dict__:
                    return player.__dict__['OwnedBrawlers']
        except:
            pass
        return {}

    def set_owned_brawlers(self, player, brawlers):
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

    def save_player_data(self, calling_instance, player):
        """Сохраняет данные игрока в БД"""
        try:
            if hasattr(calling_instance, 'db') and calling_instance.db:
                # Преобразуем игрока в JSON
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
