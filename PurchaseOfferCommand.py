from Heart.Commands.LogicCommand import LogicCommand
from Heart.Messaging import Messaging
import json
import time

class PurchaseOfferCommand(LogicCommand):
    def __init__(self, commandData):
        super().__init__(commandData)

    def encode(self, fields):
        LogicCommand.encode(self, fields)
        # Отправляем подтверждение успешной покупки
        self.writeVInt(1)  # 1 = успех, 0 = ошибка
        self.writeDataReference(0)
        self.writeVInt(0)
        return self.messagePayload

    def decode(self, calling_instance):
        fields = {}
        LogicCommand.decode(calling_instance, fields, False)
        fields["OfferIndex"] = calling_instance.readVInt()  # Индекс предложения
        fields["ShopCategory"] = calling_instance.readDataReference()  # Категория (например скины)
        fields["ItemID"] = calling_instance.readDataReference()  # ID предмета
        fields["CurrencyType"] = calling_instance.readVInt()  # 0 = гемы, 1 = монеты, 2 = звездные
        fields["Price"] = calling_instance.readVInt()  # Цена
        fields["Unk6"] = calling_instance.readVInt()  # Неизвестно, но надо прочитать
        
        LogicCommand.parseFields(fields)
        return fields

    def execute(self, calling_instance, fields):
        # Получаем игрока
        player = calling_instance.player
        if not player:
            print("[ERROR] Player not found in PurchaseOfferCommand")
            return
        
        # Извлекаем данные
        offer_index = fields.get("OfferIndex", 0)
        shop_category = fields.get("ShopCategory", [0, 0])
        item_id = fields.get("ItemID", [0, 0])
        currency_type = fields.get("CurrencyType", 0)
        price = fields.get("Price", 0)
        
        # Логируем покупку
        print(f"[PURCHASE] Player {player.get('Name', 'Unknown')} buying: cat={shop_category}, item={item_id}, price={price}, curr={currency_type}")
        
        # Проверяем баланс
        if currency_type == 0:  # Гемы
            if player.get("Gems", 0) < price:
                print(f"[ERROR] Not enough gems: has {player.get('Gems', 0)}, needs {price}")
                return
            player["Gems"] = player.get("Gems", 0) - price
            
        elif currency_type == 1:  # Монеты
            if player.get("Coins", 0) < price:
                print(f"[ERROR] Not enough coins: has {player.get('Coins', 0)}, needs {price}")
                return
            player["Coins"] = player.get("Coins", 0) - price
            
        elif currency_type == 2:  # Звездные очки
            if player.get("StarPoints", 0) < price:
                print(f"[ERROR] Not enough starpoints: has {player.get('StarPoints', 0)}, needs {price}")
                return
            player["StarPoints"] = player.get("StarPoints", 0) - price
        
        # Выдача предмета
        item_category = shop_category[0] if isinstance(shop_category, list) else 0
        item_sub_id = shop_category[1] if isinstance(shop_category, list) and len(shop_category) > 1 else 0
        
        # 16 = скины (в Brawl Stars)
        if item_category == 16:
            brawler_id = item_id[0] if isinstance(item_id, list) else 0
            skin_id = item_id[1] if isinstance(item_id, list) and len(item_id) > 1 else 0
            
            # Добавляем скин игроку
            brawler_key = str(brawler_id)
            if brawler_key in player.get("OwnedBrawlers", {}):
                if "Skins" not in player["OwnedBrawlers"][brawler_key]:
                    player["OwnedBrawlers"][brawler_key]["Skins"] = []
                if skin_id not in player["OwnedBrawlers"][brawler_key]["Skins"]:
                    player["OwnedBrawlers"][brawler_key]["Skins"].append(skin_id)
                    print(f"[PURCHASE] Skin {skin_id} for brawler {brawler_id} added to {player.get('Name')}")
        
        # 0 = ресурсы (гемы, монеты и т.д.)
        elif item_category == 0:
            # Здесь можно обработать покупку ресурсов
            pass
        
        # Сохраняем изменения в БД
        self.save_player_data(calling_instance, player)
        
        # Отправляем обновление клиенту
        self.send_home_data(calling_instance)
        
        print(f"[PURCHASE] Completed successfully for {player.get('Name')}")

    def save_player_data(self, calling_instance, player_data):
        """Сохраняет данные игрока в БД"""
        try:
            # Здесь должен быть код сохранения в БД
            # В зависимости от твоей структуры
            cursor = calling_instance.db.cursor()
            cursor.execute(
                "UPDATE main SET Data = ? WHERE Token = ?",
                (json.dumps(player_data), calling_instance.player_token)
            )
            calling_instance.db.commit()
        except Exception as e:
            print(f"[ERROR] Failed to save player data: {e}")

    def send_home_data(self, calling_instance):
        """Отправляет обновленные данные домой"""
        try:
            from Heart.Packets.Server.OwnHomeDataMessage import OwnHomeDataMessage
            home_msg = OwnHomeDataMessage(calling_instance)
            home_msg.encode()
            Messaging.send(calling_instance, home_msg.buffer)
        except Exception as e:
            print(f"[ERROR] Failed to send home data: {e}")

    def getCommandType(self):
        return 519