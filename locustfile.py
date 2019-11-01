import six

from lxml import html
from types import MethodType
from locust import HttpLocust, TaskSet, task
from locust import events
from locust.exception import CatchResponseError


class UserBehavior(TaskSet):

    HEADERS = {"Cache-Control": "max-age=0", "Origin": "https://challengers.flood.io",
               "Upgrade-Insecure-Requests": "1", "Content-Type": "application/x-www-form-urlencoded",
               "Accept": "text/html,application/xhtml + xml, application/xml;q=0.9,image/webp, image/apng,*/ *; q=0.8",
               "Accept-Encoding": "gzip, deflate, br"}

    @staticmethod
    def get_auth(request):
        tree = html.fromstring(request.content)
        auth_token = tree.cssselect('#new_challenger input[name="authenticity_token"]')[0].value
        return auth_token

    @staticmethod
    def get_step_id(request):
        tree = html.fromstring(request.content)
        step_id = tree.cssselect('#new_challenger input[name="challenger[step_id]"]')[0].value
        return step_id

    @staticmethod
    def get_max_order(request):
        tree = html.fromstring(request.content)
        ord_id = tree.cssselect('span.radio input')
        ord_value = tree.cssselect('span.radio label')
        max_val = max(map(int, [order.text for order in ord_value]))
        for k, v in zip(ord_id, ord_value):
            if int(v.text) == max_val:
                order_value = max_val
                order_id = k
                return order_value, order_id.attrib['value']

    @staticmethod
    def get_hidden_orders(request):
        tree = html.fromstring(request.content)
        inputs_to_send = tree.cssselect('.simple_form.new_challenger input[name*=challenger\[order]')
        partial_payload = {inputs_to_send[inputs_to_send.index(i)].attrib['name']: inputs_to_send[inputs_to_send.index(i)].attrib['value'] for i in inputs_to_send}
        return partial_payload

    def open_flood(self):
        r = self.client.get('/', name='/start_challenge')
        assert r.content.find("This is your entry point. Good luck!") > 0
        auth_token = self.get_auth(r)
        step_id= self.get_step_id(r)
        formdata = {
            "authenticity_token": auth_token,
            "challenger[step_id]": step_id,
            "challenger[step_number]": '1',
            "commit": "Start"
        }
        return formdata

    def start_flood(self, formdata):
        r = self.client.post('/start', headers=self.HEADERS, data=formdata, name='/select_age')
        assert r.content.find("Step 2") > 0
        step_id = self.get_step_id(r)
        auth_token = self.get_auth(r)
        formdata = {
            "authenticity_token": auth_token,
            "challenger[step_id]": step_id,
            "challenger[step_number]": '2',
            "challenger[age]": '21',
            "commit": "Next"
        }
        return formdata

    def choose_age(self, formdata):
        r = self.client.post('/start', headers=self.HEADERS, data=formdata, name='/max_order')
        assert r.content.find("Step 3") > 0
        step_id = self.get_step_id(r)
        auth_token = self.get_auth(r)
        max_order = self.get_max_order(r)
        formdata = {
            "authenticity_token": auth_token,
            "challenger[step_id]": step_id,
            "challenger[step_number]": "3",
            "challenger[largest_order]": max_order[0],
            "challenger[order_selected]": max_order[1],
            "commit": "Next"
        }
        return formdata

    def press_next_button(self, formdata):
        r = self.client.post('/start', headers=self.HEADERS, data=formdata, name='/hidden_orders')
        assert r.content.find("This step is easy!") > 0
        step_id = self.get_step_id(r)
        auth_token = self.get_auth(r)
        hidden_orders = self.get_hidden_orders(r)
        formdata = {
            "authenticity_token": auth_token,
            "challenger[step_id]": step_id,
            "challenger[step_number]": "4",
            "commit": "Next"
        }
        formdata.update(hidden_orders)
        return formdata

    def send_token(self, formdata):
        r = self.client.post('/start', headers=self.HEADERS, data=formdata, name='/token_page')
        assert r.content.find("One Time Token") > 0
        step_id = self.get_step_id(r)
        auth_token = self.get_auth(r)
        response = self.client.get('/code', headers=self.HEADERS, name='/get_token')
        formdata = {
            "authenticity_token": auth_token,
            "challenger[step_id]": step_id,
            "challenger[step_number]": "5",
            "challenger[one_time_token]": response.json()['code'],
            "commit": "Next"
        }
        return formdata

    def final_page(self, formdata):
        r = self.client.post('/start', headers=self.HEADERS, data=formdata, name='/final_page')
        assert r.content.find("You're Done!") > 0

    @task
    def test_case(self):
        step_one_data = self.open_flood()
        step_two_data = self.start_flood(step_one_data)
        step_three_data = self.choose_age(step_two_data)
        step_four_data = self.press_next_button(step_three_data)
        step_five_data = self.send_token(step_four_data)
        self.final_page(step_five_data)


class WebsiteUser(HttpLocust):
    host = "https://challengers.flood.io"
    task_set = UserBehavior
    min_wait = 1000
    max_wait = 2000


if __name__ == '__main__':
    WebsiteUser().run()
