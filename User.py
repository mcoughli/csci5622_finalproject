from _collections import defaultdict


class User:
    def __init__(self, u_id):
        self.u_id = u_id
        self.average_position = 0
        self.num_questions = 0
        self.num_correct = 0
        self.num_incorrect = 0
        self.questions = {}
        self.category_averages = defaultdict(lambda: [0.0, 0.0, 0.0])
        
    def add_question(self, q_id, correct, position, answer, category):
        self.questions[q_id] = {'q_id':q_id, 'correct':correct, 'position':position, 'answer':answer}
        current_total = self.num_questions#self.num_correct + self.num_incorrect
        current_position_sum = self.average_position*current_total
        updated_total = current_total + 1
        updated_sum = current_position_sum + position
        self.average_position = updated_sum/updated_total
        if correct:
            self.num_correct = self.num_correct + 1
        else:
            self.num_incorrect = self.num_incorrect + 1
        self.num_questions = self.num_questions + 1
        current_category_data = self.category_averages[category]
        current_category_average = current_category_data[0]
        current_category_running_total = current_category_data[1]
        current_category_count = current_category_data[2]
        current_category_running_total += position
        current_category_count += 1
        current_category_average = current_category_running_total/current_category_count
        new_category_data = [current_category_average, current_category_running_total, current_category_count]
        self.category_averages[category] = new_category_data