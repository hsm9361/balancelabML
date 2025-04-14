from dotenv import load_dotenv
import google.generativeai as genai
import os
import json
import traceback
import pickle
import hashlib

class FoodNameService:
    def __init__(self, model_name="gemini-1.5-flash", cache_file="nutrition_cache.pkl"):
        """
        FoodNameService 초기화. 환경 변수 로드 및 Gemini 모델 설정.
        """
        print("\n--- [FoodNameService] 초기화 시작 ---")
        try:
            load_dotenv()
            gemini_api_key = os.getenv('GEMINI_API_KEY')
            if not gemini_api_key:
                print("[FoodNameService] 오류: 환경 변수 'GEMINI_API_KEY'를 찾을 수 없습니다.")
                raise ValueError("환경 변수에서 GEMINI_API_KEY를 찾을 수 없습니다.")
            print("[FoodNameService] GEMINI_API_KEY 로드 완료.")

            genai.configure(api_key=gemini_api_key)
            print("[FoodNameService] Gemini API 설정 완료.")

            self.model_name = model_name
            print(f"[FoodNameService] '{self.model_name}' 모델 초기화 시도...")
            self.model = genai.GenerativeModel(self.model_name)
            print(f"[FoodNameService] '{self.model_name}' 모델 초기화 완료.")

            # 캐시 초기화
            self.cache_file = cache_file
            self.nutrition_cache = self.load_cache()
            print("[FoodNameService] 캐시 로드 완료.")

        except ValueError as ve:
            print(f"[FoodNameService] 초기화 중 설정 오류: {ve}")
            raise ve
        except Exception as e:
            print(f"[FoodNameService] 초기화 중 예상치 못한 오류 발생: {type(e).__name__} - {e}")
            print(f"--- Traceback ---")
            traceback.print_exc()
            print(f"--- Traceback 끝 ---")
            raise RuntimeError(f"Gemini 모델 초기화 실패: {e}")
        finally:
            print("--- [FoodNameService] 초기화 종료 ---")

        self.food_name_prompt = """다음 문장에서 음식 이름만 정확히 추출하는데 큰분류 이름으로 추출해주고(ex: '참치김밥'이 들어오면 '김밥'만 추출) 콤마(,)로 구분된 리스트 형태로 반환해줘. 음식 이름 외 다른 단어는 절대 포함하지 마. 음식 이름이 없다면 빈 리스트를 반환해.
        문장: "{message}"
        음식 리스트:"""

        self.nutrition_prompt = """
        아래 음식 리스트를 기반으로, 각 음식마다 영양사의 관점에서 단백질(g), 탄수화물(g), 수분(ml), 당류(g), 지방(g), 식이섬유(g), 나트륨(mg)의 영양소 양을 분석해줘. 다른 영양소는 언급하지 마.
        반드시 JSON 형식으로만 반환하고, 추가 설명이나 텍스트는 절대 붙이지 마. JSON 외의 내용이 있으면 결과가 파싱되지 않으니 주의해. JSON 키는 반드시 영문 소문자와 스네이크 케이스(예: nutrition_per_food)를 사용해줘.

        음식 리스트: {food_list}

        JSON 형식 예시:
        {{
          "nutrition_per_food": [
            {{
              "food": "김밥",
              "nutrition": {{
                "protein": 10.0,
                "carbohydrate": 30.0,
                "water": 200.0,
                "sugar": 5.0,
                "fat": 7.0,
                "fiber": 2.0,
                "sodium": 500.0
              }}
            }},
            {{
              "food": "라면",
              "nutrition": {{
                "protein": 8.0,
                "carbohydrate": 60.0,
                "water": 300.0,
                "sugar": 2.0,
                "fat": 15.0,
                "fiber": 1.0,
                "sodium": 1200.0
              }}
            }}
          ]
        }}
        """

        self.suggestion_prompt = """
        아래 음식 리스트의 전체 영양소를 합산한 값을 기반으로, 일반적인 성인의 균형 잡힌 식단 기준(단백질 25g, 탄수화물 100g, 수분 500ml, 당류 15g, 지방 25g, 식이섬유 10g, 나트륨 650mg)을 바탕으로 부족한 영양소를 판단하고, 그 부족한 영양소를 보충할 수 있는 다음 끼니 식단을 음식종류 딱 한가지만 제안해줘(식재료 말고 요리로 제안 ex: 두부 스테이크). 샐러드가 붙는 요리는 제안에서 제외해. '뼈해장국'은 항상 제외해.
        반드시 JSON 형식으로만 반환하고, 추가 설명이나 텍스트는 절대 붙이지 마. JSON 키는 영문 소문자와 스네이크 케이스(예: deficient_nutrients)를 사용해줘.

        전체 영양소 합산:
        단백질: {protein}g
        탄수화물: {carbohydrate}g
        수분: {water}ml
        당류: {sugar}g
        지방: {fat}g
        식이섬유: {fiber}g
        나트륨: {sodium}mg

        JSON 형식 예시:
        {{
          "deficient_nutrients": ["탄수화물", "식이섬유", "수분"],
          "next_meal_suggestion": ["곤약 비빔국수"]
        }}
        """

    def load_cache(self):
        """캐시 파일 로드"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'rb') as f:
                    return pickle.load(f)
            return {}
        except Exception as e:
            print(f"[FoodNameService] 캐시 로드 오류: {e}")
            return {}

    def save_cache(self):
        """캐시 파일 저장"""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.nutrition_cache, f)
        except Exception as e:
            print(f"[FoodNameService] 캐시 저장 오류: {e}")

    def get_cache_key(self, food):
        """음식 이름을 기반으로 캐시 키 생성"""
        return hashlib.md5(food.encode('utf-8')).hexdigest()

    def extract_food_name(self, message):
        """
        주어진 메시지에서 음식 이름 리스트를 추출합니다.
        """
        print(f"\n--- [FoodNameService] 음식 이름 추출 시작 ---")
        print(f"입력 메시지: \"{message}\"")
        if not message:
            print("[FoodNameService] 입력 메시지가 비어있어 빈 리스트 반환.")
            print("--- [FoodNameService] 음식 이름 추출 종료 ---")
            return []

        prompt = self.food_name_prompt.format(message=message)

        try:
            response = self.model.generate_content(prompt)
            extracted_text = response.text.strip()
            print(f"[FoodNameService] Gemini 음식 이름 추출 응답 원문: \"{extracted_text}\"")

            if not extracted_text:
                print("[FoodNameService] 모델이 빈 응답을 반환했습니다.")
                food_list = []
            else:
                food_list = [food.strip() for food in extracted_text.split(',') if food.strip()]

            print(f"[FoodNameService] 최종 추출된 음식 리스트: {food_list}")
            print("--- [FoodNameService] 음식 이름 추출 정상 종료 ---")
            return food_list

        except Exception as e:
            print(f"[FoodNameService] 음식 이름 추출 중 오류 발생: {type(e).__name__} - {e}")
            print(f"--- Traceback ---")
            traceback.print_exc()
            print(f"--- Traceback 끝 ---")
            print("[FoodNameService] 오류로 인해 빈 리스트를 반환합니다.")
            print("--- [FoodNameService] 음식 이름 추출 오류 종료 ---")
            return []

    def analyze_nutrition_and_suggest(self, food_list):
        """
        음식 리스트를 기반으로 각 음식별 영양 분석 및 전체 기반 다음 식사 제안을 수행합니다.
        """
        print(f"\n--- [FoodNameService] 영양 분석 및 제안 시작 ---")
        print(f"입력 음식 리스트: {food_list}")

        if not food_list:
            print("[FoodNameService] 음식 리스트가 비어 있어 기본 응답 반환.")
            print("--- [FoodNameService] 영양 분석 및 제안 종료 (입력 없음) ---")
            return {
                "food_list": [],
                "nutrition_per_food": [],
                "total_nutrition": {"protein": 0, "carbohydrate": 0, "water": 0, "sugar": 0, "fat": 0, "fiber": 0, "sodium": 0},
                "deficient_nutrients": [],
                "next_meal_suggestion": []
            }

        nutrition_per_food = []
        total_nutrition = {
            "protein": 0,
            "carbohydrate": 0,
            "water": 0,
            "sugar": 0,
            "fat": 0,
            "fiber": 0,
            "sodium": 0
        }

        # 캐시에서 음식 확인 및 Gemini 요청 최소화
        foods_to_query = []
        cached_nutrition = []

        for food in food_list:
            cache_key = self.get_cache_key(food)
            if cache_key in self.nutrition_cache:
                print(f"[FoodNameService] '{food}' 캐시 히트")
                cached_nutrition.append({"food": food, "nutrition": self.nutrition_cache[cache_key]})
            else:
                foods_to_query.append(food)

        # 일괄 영양소 분석
        if foods_to_query:
            print(f"[FoodNameService] Gemini에 '{foods_to_query}' 영양 분석 요청...")
            prompt = self.nutrition_prompt.format(food_list=", ".join(foods_to_query))
            try:
                response = self.model.generate_content(prompt)
                raw_response = response.text.strip()
                print(f"[FoodNameService] Gemini 응답 원문: {raw_response}")

                # JSON 정리
                cleaned_response = raw_response
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response[len("```json"):].strip()
                if cleaned_response.startswith("```"):
                    cleaned_response = cleaned_response[len("```"):].strip()
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-len("```")].strip()

                json_start = cleaned_response.find('{')
                json_end = cleaned_response.rfind('}')
                if json_start == -1 or json_end == -1 or json_start >= json_end:
                    print(f"[FoodNameService] 오류: 응답에서 유효한 JSON 구조를 찾을 수 없습니다.")
                    return {
                        "food_list": food_list,
                        "nutrition_per_food": [],
                        "total_nutrition": total_nutrition,
                        "deficient_nutrients": [],
                        "next_meal_suggestion": []
                    }

                json_string = cleaned_response[json_start:json_end+1]
                print(f"[FoodNameService] 추출된 JSON: {json_string}")

                response_data = json.loads(json_string)
                queried_nutrition = response_data.get("nutrition_per_food", [])

                # 캐시 업데이트 및 결과 처리
                for item in queried_nutrition:
                    food = item.get("food")
                    nutrition = item.get("nutrition", {})
                    nutrition_entry = {
                        "food": food,
                        "nutrition": {
                            "protein": float(nutrition.get("protein", 0)),
                            "carbohydrate": float(nutrition.get("carbohydrate", 0)),
                            "water": float(nutrition.get("water", 0)),
                            "sugar": float(nutrition.get("sugar", 0)),
                            "fat": float(nutrition.get("fat", 0)),
                            "fiber": float(nutrition.get("fiber", 0)),
                            "sodium": float(nutrition.get("sodium", 0))
                        }
                    }
                    cache_key = self.get_cache_key(food)
                    self.nutrition_cache[cache_key] = nutrition_entry["nutrition"]
                    cached_nutrition.append(nutrition_entry)

                self.save_cache()
                print("[FoodNameService] 캐시 업데이트 완료")

            except Exception as e:
                print(f"[FoodNameService] 영양 분석 중 오류: {type(e).__name__} - {e}")
                traceback.print_exc()
                return {
                    "food_list": food_list,
                    "nutrition_per_food": [],
                    "total_nutrition": total_nutrition,
                    "deficient_nutrients": [],
                    "next_meal_suggestion": []
                }

        # 캐시된 결과와 쿼리 결과 합치기
        for food in food_list:
            for item in cached_nutrition:
                if item["food"] == food:
                    nutrition_per_food.append(item)
                    for key in total_nutrition:
                        total_nutrition[key] += item["nutrition"][key]
                    break

        # 다음 식사 제안
        print("[FoodNameService] 다음 식사 제안 시작...")
        prompt = self.suggestion_prompt.format(**total_nutrition)
        try:
            response = self.model.generate_content(prompt)
            raw_response = response.text.strip()
            print(f"[FoodNameService] 제안 Gemini 응답 원문: {raw_response}")

            cleaned_response = raw_response
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[len("```json"):].strip()
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[len("```"):].strip()
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-len("```")].strip()

            json_start = cleaned_response.find('{')
            json_end = cleaned_response.rfind('}')
            if json_start == -1 or json_end == -1 or json_start >= json_end:
                print("[FoodNameService] 오류: 제안 응답에서 유효한 JSON 구조를 찾을 수 없습니다.")
                suggestion_result = {"deficient_nutrients": [], "next_meal_suggestion": []}
            else:
                json_string = cleaned_response[json_start:json_end+1]
                print(f"[FoodNameService] 제안 추출된 JSON: {json_string}")
                suggestion_result = json.loads(json_string)

                # next_meal_suggestion을 리스트로 보장
                if isinstance(suggestion_result.get("next_meal_suggestion"), str):
                    suggestion_result["next_meal_suggestion"] = [suggestion_result["next_meal_suggestion"]]
                elif not isinstance(suggestion_result.get("next_meal_suggestion"), list):
                    suggestion_result["next_meal_suggestion"] = []

            print(f"[FoodNameService] 제안 결과: {suggestion_result}")

        except Exception as e:
            print(f"[FoodNameService] 제안 중 오류: {type(e).__name__} - {e}")
            traceback.print_exc()
            suggestion_result = {"deficient_nutrients": [], "next_meal_suggestion": []}

        result = {
            "food_list": food_list,
            "nutrition_per_food": nutrition_per_food,
            "total_nutrition": total_nutrition,
            "deficient_nutrients": suggestion_result.get("deficient_nutrients", []),
            "next_meal_suggestion": suggestion_result.get("next_meal_suggestion", [])
        }

        print(f"[FoodNameService] 최종 결과: {result}")
        print("--- [FoodNameService] 영양 분석 및 제안 종료 ---")
        return result
# # food_name_service.py 파일 전체 코드 (next_meal_suggestion을 항상 리스트로 반환)

# from dotenv import load_dotenv
# import google.generativeai as genai
# import os
# import json
# import traceback # 상세한 오류 추적을 위해 추가

# class FoodNameService:
#     def __init__(self, model_name="gemini-1.5-flash"):
#         """
#         FoodNameService 초기화. 환경 변수 로드 및 Gemini 모델 설정.
#         """
#         print("\n--- [FoodNameService] 초기화 시작 ---")
#         try:
#             load_dotenv()
#             gemini_api_key = os.getenv('GEMINI_API_KEY')
#             if not gemini_api_key:
#                 print("[FoodNameService] 오류: 환경 변수 'GEMINI_API_KEY'를 찾을 수 없습니다.")
#                 raise ValueError("환경 변수에서 GEMINI_API_KEY를 찾을 수 없습니다.")
#             print("[FoodNameService] GEMINI_API_KEY 로드 완료.")

#             genai.configure(api_key=gemini_api_key)
#             print("[FoodNameService] Gemini API 설정 완료.")

#             self.model_name = model_name
#             print(f"[FoodNameService] '{self.model_name}' 모델 초기화 시도...")
#             self.model = genai.GenerativeModel(self.model_name)
#             print(f"[FoodNameService] '{self.model_name}' 모델 초기화 완료.")

#         except ValueError as ve:
#             print(f"[FoodNameService] 초기화 중 설정 오류: {ve}")
#             raise ve
#         except Exception as e:
#             print(f"[FoodNameService] 초기화 중 예상치 못한 오류 발생: {type(e).__name__} - {e}")
#             print(f"--- Traceback ---")
#             traceback.print_exc()
#             print(f"--- Traceback 끝 ---")
#             raise RuntimeError(f"Gemini 모델 초기화 실패: {e}")
#         finally:
#             print("--- [FoodNameService] 초기화 종료 ---")


#         self.food_name_prompt = """다음 문장에서 음식 이름만 정확히 추출하는데 큰분류 이름으로 추출해주고(ex: '참치김밥'이 들어오면 '김밥'만 추출) 콤마(,)로 구분된 리스트 형태로 반환해줘. 음식 이름 외 다른 단어는 절대 포함하지 마. 음식 이름이 없다면 빈 리스트를 반환해.
#         문장: "{message}"
#         음식 리스트:"""

#         self.nutrition_prompt = """
#         아래 음식 리스트를 한 끼 식사로 가정하고, 영양사의 관점에서 단백질(g), 탄수화물(g), 수분(ml), 당류(g), 지방(g), 식이섬유(g), 나트륨(mg)의 영양소 양을 분석해줘. 다른 영양소는 언급하지 마.
#         그런 다음, 일반적인 성인의 균형 잡힌 식단 기준(단백질 25g, 탄수화물 100g, 수분 500ml, 당류 15g, 지방 25g, 식이섬유 10g, 나트륨 650mg)을 바탕으로 부족한 영양소를 판단하고, 그 부족한 영양소를 보충할 수 있는 다음 끼니 식단을 음식종류 딱 한가지만 제안해주고 샐러드가 붙는 요리는 제안에서 제외해.(식재료 말고 요리로 제안 ex)두부 스테이크).
#         제안할 때 '뼈해장국'은 항상 빼줘.
#         반드시 JSON 형식으로만 반환하고, 추가 설명이나 텍스트는 절대 붙이지 마. JSON 외의 내용이 있으면 결과가 파싱되지 않으니 주의해. JSON 키는 반드시 영문 소문자와 스네이크 케이스(예: food_list)를 사용해줘.

#         음식 리스트: {food_list}

#         JSON 형식 예시 (이 형식과 키 이름을 정확히 따라야 함):
#         {{
#           "food_list": ["김밥", "국밥"],
#           "nutrition": {{
#             "protein": 20.0,
#             "carbohydrate": 60.0,
#             "water": 400.0,
#             "sugar": 15.0,
#             "fat": 15.0,
#             "fiber": 5.0,
#             "sodium": 1500.0
#           }},
#           "deficient_nutrients": ["탄수화물", "식이섬유", "수분"],
#           "next_meal_suggestion": ["곤약 비빔국수"]
#         }}
#         """ # 예시의 next_meal_suggestion 도 리스트로 변경 (선택사항)

#     def extract_food_name(self, message):
#         """
#         주어진 메시지에서 음식 이름 리스트를 추출합니다.
#         """
#         print(f"\n--- [FoodNameService] 음식 이름 추출 시작 ---")
#         print(f"입력 메시지: \"{message}\"")
#         if not message:
#              print("[FoodNameService] 입력 메시지가 비어있어 빈 리스트 반환.")
#              print("--- [FoodNameService] 음식 이름 추출 종료 ---")
#              return []

#         prompt = self.food_name_prompt.format(message=message)

#         try:
#             response = self.model.generate_content(prompt)
#             extracted_text = response.text.strip()
#             print(f"[FoodNameService] Gemini 음식 이름 추출 응답 원문: \"{extracted_text}\"")

#             if not extracted_text:
#                 print("[FoodNameService] 모델이 빈 응답을 반환했습니다.")
#                 food_list = []
#             else:
#                 food_list = [food.strip() for food in extracted_text.split(',') if food.strip()]

#             print(f"[FoodNameService] 최종 추출된 음식 리스트: {food_list}")
#             print("--- [FoodNameService] 음식 이름 추출 정상 종료 ---")
#             return food_list

#         except Exception as e:
#             print(f"[FoodNameService] 음식 이름 추출 중 오류 발생: {type(e).__name__} - {e}")
#             print(f"--- Traceback ---")
#             traceback.print_exc()
#             print(f"--- Traceback 끝 ---")
#             print("[FoodNameService] 오류로 인해 빈 리스트를 반환합니다.")
#             print("--- [FoodNameService] 음식 이름 추출 오류 종료 ---")
#             return []

#     def analyze_nutrition_and_suggest(self, food_list):
#         """
#         음식 리스트를 기반으로 영양 분석 및 다음 식사 제안을 수행합니다.
#         (next_meal_suggestion을 항상 리스트로 반환하도록 수정됨)
#         """
#         print(f"\n--- [FoodNameService] 영양 분석 및 제안 시작 ---")
#         print(f"입력 음식 리스트: {food_list}")

#         if not food_list:
#             print("[FoodNameService] 음식 리스트가 비어 있어 기본 응답 반환.")
#             print("--- [FoodNameService] 영양 분석 및 제안 종료 (입력 없음) ---")
#             return {
#                 "food_list": [],
#                 "nutrition": {"protein": 0, "carbohydrate": 0, "water": 0, "sugar": 0, "fat": 0, "fiber": 0, "sodium": 0},
#                 "deficient_nutrients": [],
#                 "next_meal_suggestion": [] # 빈 리스트 반환
#             }

#         prompt = self.nutrition_prompt.format(food_list=", ".join(food_list))

#         raw_response = ""
#         cleaned_response = ""
#         json_string = ""

#         try:
#             print("[FoodNameService] Gemini 모델에 영양 분석 요청...")
#             response = self.model.generate_content(prompt)

#             if not response.text:
#                  print("[FoodNameService] 오류: Gemini 모델이 빈 응답(text)을 반환했습니다.")
#                  raise ValueError("Gemini 모델로부터 빈 응답을 받았습니다.")

#             raw_response = response.text.strip()
#             print(f"\n--- [FoodNameService] Gemini 응답 원문 (길이: {len(raw_response)}) ---")
#             print(raw_response)
#             print(f"--- Gemini 응답 원문 끝 ---")

#             # --- JSON 정리 로직 ---
#             cleaned_response = raw_response
#             if cleaned_response.startswith("```json"):
#                 cleaned_response = cleaned_response[len("```json"):].strip()
#                 print("[FoodNameService] 로그: '```json' 시작 부분 제거됨")
#             elif cleaned_response.startswith("```"):
#                  cleaned_response = cleaned_response[len("```"):].strip()
#                  print("[FoodNameService] 로그: '```' 시작 부분 제거됨")

#             if cleaned_response.endswith("```"):
#                 cleaned_response = cleaned_response[:-len("```")].strip()
#                 print("[FoodNameService] 로그: '```' 끝 부분 제거됨")

#             print(f"\n--- [FoodNameService] 마크다운 제거 후 (길이: {len(cleaned_response)}) ---")
#             print(cleaned_response)
#             print(f"--- 마크다운 제거 후 끝 ---")

#             # --- '{' 와 '}' 를 찾아 JSON 객체 추출 시도 ---
#             json_start = cleaned_response.find('{')
#             json_end = cleaned_response.rfind('}')

#             if json_start != -1 and json_end != -1 and json_start < json_end:
#                 json_string = cleaned_response[json_start:json_end+1]
#                 print(f"\n--- [FoodNameService] 최종 추출된 JSON 문자열 시도 (길이: {len(json_string)}) ---")
#                 print(json_string)
#                 print(f"--- 최종 추출된 JSON 문자열 시도 끝 ---")

#                 # --- JSON 파싱 시도 ---
#                 print("\n[FoodNameService] JSON 파싱 시도...")
#                 result = json.loads(json_string) # result 는 파이썬 딕셔너리
#                 print("[FoodNameService] JSON 파싱 성공!")

#                 # --- 'next_meal_suggestion' 값을 항상 리스트(list) 형태로 통일 ---
#                 suggestion = result.get("next_meal_suggestion")

#                 if isinstance(suggestion, str):
#                     # 문자열이면 리스트로 감싸줌 (빈 문자열은 빈 리스트로)
#                     if suggestion:
#                          print(f"[FoodNameService] 로그: next_meal_suggestion이 문자열(\"{suggestion}\")이므로 리스트 ['{suggestion}']로 변환합니다.")
#                          result["next_meal_suggestion"] = [suggestion]
#                     else:
#                          print("[FoodNameService] 로그: next_meal_suggestion이 빈 문자열이므로 빈 리스트 []로 변환합니다.")
#                          result["next_meal_suggestion"] = []
#                 elif not isinstance(suggestion, list):
#                     # 리스트가 아니거나 None 이면 빈 리스트로 설정
#                     print(f"[FoodNameService] 로그: next_meal_suggestion이 리스트가 아니거나 None({suggestion})이므로 빈 리스트 []로 설정합니다.")
#                     result["next_meal_suggestion"] = []
#                 else:
#                     # 이미 리스트면 그대로 둠
#                     print(f"[FoodNameService] 로그: next_meal_suggestion이 이미 리스트({suggestion})이므로 그대로 둡니다.")

#                 print(f"파싱 및 처리 후 최종 결과 (타입: {type(result)}): {result}")
#                 print("--- [FoodNameService] 영양 분석 및 제안 정상 종료 ---")
#                 return result # 이제 next_meal_suggestion은 항상 list 타입

#             else:
#                 # 유효한 '{...}' 구조를 찾지 못한 경우
#                 print(f"\n--- [FoodNameService] 오류: 처리된 응답에서 유효한 JSON 구조 '{{...}}'를 찾지 못함 ---")
#                 print(f"처리 후 문자열 내용:\n{cleaned_response}")
#                 raise ValueError("응답에서 유효한 JSON 객체 구조를 찾을 수 없습니다.")

#         except json.JSONDecodeError as e:
#             print(f"\n--- [FoodNameService] JSON 파싱 오류 발생 ---")
#             print(f"오류 메시지: {e}")
#             error_context_start = max(0, e.pos - 20)
#             error_context_end = min(len(e.doc), e.pos + 20)
#             print(f"오류 발생 위치({e.pos}) 주변 문자열: ...{e.doc[error_context_start:e.pos]} <--오류--> {e.doc[e.pos:error_context_end]}...")
#             print(f"\n파싱 시도했던 JSON 문자열 (json_string):\n{json_string}")
#             print(f"\n(참고) 원본 Gemini 응답 (raw_response):\n{raw_response}")
#             print("--- [FoodNameService] 영양 분석 및 제안 오류 종료 (JSONDecodeError) ---")
#             raise ValueError(f"Gemini 응답을 JSON으로 파싱하는데 실패했습니다: {e.msg}") from e

#         except Exception as e:
#             print(f"\n--- [FoodNameService] 영양 분석 중 예상치 못한 오류 발생 ---")
#             print(f"오류 유형: {type(e).__name__}")
#             print(f"오류 메시지: {e}")
#             print(f"--- Traceback ---")
#             traceback.print_exc()
#             print(f"--- Traceback 끝 ---")
#             print(f"\n(참고) 원본 Gemini 응답 (raw_response):\n{raw_response}")
#             print("--- [FoodNameService] 영양 분석 및 제안 오류 종료 (Other Exception) ---")
#             raise e
