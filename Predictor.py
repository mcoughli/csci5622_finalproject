from csv import DictWriter
import csv
import datetime
from math import ceil
from multiprocessing import Manager, Pool
from multiprocessing import Value
from multiprocessing.process import Process
from numpy import sign
from numpy.ctypeslib import ctypes
import os
import pickle
import random
from sklearn import ensemble, svm, neighbors, gaussian_process, kernel_ridge
from sklearn.linear_model.stochastic_gradient import SGDClassifier
from sklearn.metrics.regression import mean_squared_error
from sklearn.tree.tree import DecisionTreeRegressor
import time

from Analyzer import Analyzer
from Category import Category
from Example import Example
from Featurizer import Featurizer
from Question import Question
from User import User
from duplicity.tempdir import default
from _collections import defaultdict


class Predictor:
    def __init__(self, input_args, position_features, correctness_features, n_estimators=650, 
                 cluster=False, num_clusters=3, cluster_boundaries=[10,50,100], skip_clusters=[],
                 cluster_training_data=False):
        self.args = input_args
        self.position_features = position_features
        self.correctness_features = correctness_features
        self.n_estimators = n_estimators
        self.cluster = cluster
        self.num_clusters = 3
        self.cluster_boundaries = cluster_boundaries
        self.skip_clusters = skip_clusters
        self.cluster_training_data=cluster_training_data
    
    def stringToInt(self, s):
        return int(float(s))  
      
        
    def rootMeanSquaredError(self, examples):
        predictions = [x.prediction for x in examples]
        observations = [x.observation for x in examples]
        return mean_squared_error(predictions, observations) ** 0.5
    
    def recordErrors(self, errorFileName, examples, users, categories):
        sortedExamples = sorted(examples, key=lambda ex:self.rootMeanSquaredError([ex]), reverse=True)
        errorFile = open(errorFileName, 'w')
        errorFile.write("Example ID,RMS ERROR,User ID,Num Incorrect,User Average,Questions Answered,"+
        "Category,Q Average,Category Average,Actual Response Time,Predicted Response Time,"+
        "Q Length,Q Correct,Q Incorrect,Q Answer,Q\n")
        for ex in sortedExamples:
            raw_question_words = []
            for tuple in ex.question.question:
                raw_question_words.append(tuple[0])
            raw_question = " ".join(raw_question_words)
            raw_question = raw_question.replace(",","_")
            errorFile.write(",".join([str(ex.id), str(self.rootMeanSquaredError([ex])), str(ex.user), str(users[ex.user].num_incorrect), str(users[ex.user].average_position), str(users[ex.user].num_questions),
                                       str(ex.question.category),str(ex.question.average_response), str(categories[ex.question.category].average),str(ex.observation), str(ex.prediction), 
                                       str(len(raw_question.split())), str(ex.question.num_correct), str(ex.question.num_incorrect), ex.question.answer, str(raw_question)])+"\n")
        errorFile.flush()
        errorFile.close()
        
    def producePredictionsProcess(self, cluster, cluster_index, cluster_ranges, 
                                  continuous_features_in, binary_features_in, category_dict, 
                                  users, wiki_data, trainingExamples, clusters_out, err_val):
        
        second_stage_features = ['previous_prediction']
        continuous_features = defaultdict(lambda: False)
        binary_features = defaultdict(lambda: False)
        continuous_second_stage_features = []
        binary_second_stage_features = []
        perform_second_stage = False
        for feature in continuous_features_in:
            continuous_features[feature] = continuous_features_in[feature]
        for feature in binary_features_in:
            binary_features[feature] = binary_features_in[feature]
        
        for feature in continuous_features:
            if feature in second_stage_features and continuous_features[feature]:
                continuous_second_stage_features.append(feature)
                perform_second_stage = True
                continuous_features[feature] = False
                print "Removing feature: "+str(feature)
        
        analyzer_abs = Analyzer(features=continuous_features)
        featurizer_abs = Featurizer(category_dict, features=continuous_features, use_default=False, analyzer=analyzer_abs)
        
        
        
        analyzer_sign = Analyzer(features=binary_features)
        featurizer_sign = Featurizer(category_dict, features=binary_features, use_default=False, analyzer=analyzer_sign)
        range_string = str(cluster_ranges[cluster_index][0])+" - "+str(cluster_ranges[cluster_index][1])
    #     featurizer = Featurizer(use_default=True)
        y_train_abs = []
        y_train_sign = []
        for train_example in trainingExamples:
            y_train_abs.append(train_example.observation)
#                 y_train_abs.append(abs(train_example.observation))
#                 y_train_sign.append(sign(train_example.observation))
        print "Generating continuous training x for range: "+range_string
        x_train_abs = featurizer_abs.train_feature(trainingExamples, users, wiki_data)
#             print featurizer_abs.vectorizer.vocabulary_.get('document')
    #     for feat in x_train:
    #         print feat
#             print x_train_abs.toarray()[0]
#             print x_train_abs.toarray()[50]
    # #     print x_train.toarray()[4000]
    # #     del trainingExamples
        print "Generating continuous test x for range: "+range_string
#             x_test_abs = featurizer_abs.test_feature(testExamples, users, wiki_data)
        x_test_abs = featurizer_abs.test_feature(cluster, users, wiki_data)
          
          
    #     classifier = SGDClassifier(loss='log', penalty='l2', shuffle=True)
    #     
    #     lr.fit(x_train, y_train)
      
    #     continuous_classifier = linear_model.LinearRegression()
    #     continuous_classifier = svm.NuSVR()
        if 'kernel' in continuous_features:
            kernel = continuous_features['kernel']
        else:
            kernel = 'rbf'
        if 'continuous_classifier' in continuous_features:
            classifier_type = continuous_features['continuous_classifier']
        else:
            classifier_type = False
        if not classifier_type or classifier_type == 'ensemble_gradientboost':
            continuous_classifier = ensemble.GradientBoostingRegressor(n_estimators=self.n_estimators)
        elif classifier_type == 'svr':
            continuous_classifier = svm.NuSVR(kernel=kernel, )#svm.SVR(kernel=kernel)
        elif classifier_type == 'gaussian_process':
            continuous_classifier = gaussian_process.GaussianProcess(storage_mode='light')
        elif classifier_type == 'decision_tree_regressor':
            continuous_classifier = DecisionTreeRegressor()
        elif classifier_type == 'kernel_ridge':
            continuous_classifier = kernel_ridge.KernelRidge(kernel=kernel)
        elif classifier_type == 'ensemble_adaboost':
            continuous_classifier = ensemble.AdaBoostRegressor(n_estimators=self.n_estimators)
        elif classifier_type == 'ensemble_randomforest':
            continuous_classifier = ensemble.RandomForestRegressor(n_estimators=self.n_estimators)
        elif classifier_type == 'ensemble_bagging':
            continuous_classifier = ensemble.BaggingRegressor()
        else:
            continuous_classifier = ensemble.GradientBoostingRegressor(n_estimators=self.n_estimators)
    #     continuous_classifier = ensemble.AdaBoostRegressor(n_estimators=4000)
    #     continuous_classifier = ensemble.RandomForestRegressor()
    #     continuous_classifier = ensemble.BaggingRegressor()
          
        print "Fitting continuous classifier for range: "+range_string  
        continuous_classifier.fit(x_train_abs.toarray(), y_train_abs)  
          
        print "Fit continuous training data for range: "+range_string
    #     
        print "Predicting continuous classifier for range: "+range_string
        predictions_abs = continuous_classifier.predict(x_test_abs.toarray())
        
        if perform_second_stage:
            print "Length of predictions before second stage: "+str(len(predictions_abs))
            for i in range(len(predictions_abs)):
                current_sign = sign(predictions_abs[i])
                current_abs = abs(predictions_abs[i])
                current_question = cluster[i].question
                if current_abs >= current_question.length:
                    current_abs = current_question.length
    #             cluster[i].prediction = int(ceil(random.choice([1, -1])*current_abs))
                cluster[i].previous_prediction = int(ceil(current_sign*current_abs))
            
            second_stage_features_dict = continuous_features#defaultdict(lambda: False)
            for feature in continuous_second_stage_features:
                print "Adding feature: "+str(feature)
                second_stage_features_dict[feature] = True
            analyzer_abs = Analyzer(features=second_stage_features_dict)
            featurizer_abs = Featurizer(category_dict, features=second_stage_features_dict, use_default=False, analyzer=analyzer_abs)
            
            print "Generating second stage training X for range: "+range_string
            x_train_abs = featurizer_abs.train_feature(trainingExamples, users, wiki_data, skip_vectorizer=False)
#             print x_train_abs.toarray()
            
            print "Generating second stage test X for range: "+range_string
            x_test_abs = featurizer_abs.test_feature(cluster, users, wiki_data, skip_vectorizer=False)
#             print x_test_abs.toarray()
            
            print "Fitting second stage training data for range: "+range_string
            continuous_classifier.fit(x_train_abs.toarray(), y_train_abs)  
            
            print "Predicting second stage continuous classifier for range: "+range_string
            predictions_abs = continuous_classifier.predict(x_test_abs.toarray())
    #     print predictions_abs
        
#             binary_classifier = SGDClassifier(loss='log', penalty='l2', shuffle=True)
        
#             binary_classifier = svm.SVC(kernel=kernel, class_weight='auto')
#             binary_classifier = ensemble.GradientBoostingClassifier(n_estimators=1000)
# #             binary_classifier = neighbors.KNeighborsClassifier()
#             print "Fitting binary classifier"
#             print "Generating binary text x"
#             print "Generating binary training x"
#             
#             x_train_sign = featurizer_sign.train_feature(trainingExamples, users, wiki_data)
#             
#             x_test_sign = featurizer_sign.test_feature(cluster, users, wiki_data)
#         #     
#         #     
#             binary_classifier = svm.SVC(kernel=kernel)
#         #     print x_test_sign.toarray()[0]
#         #     print x_train_sign.toarray()[0]
#         # #     binary_classifier = neural_network.BernoulliRBM()
#             binary_classifier.fit(x_train_sign.toarray(), y_train_sign)
#         #     
#             print "Fit binary classifier"
#             print "Predicting binary classifier"
#             predictions_binary = binary_classifier.predict(x_test_sign.toarray())
#             
#         #     print predictions_binary
#             print "Features importance:"
#             print continuous_classifier.feature_importances_
        
#             for i in range(len(predictions_abs)):
#                 current_prediction = int(ceil(predictions_abs[i]))
#                 current_question = cluster[i].question
#                 current_question_min = current_question.min
#                 if current_question.num_correct > current_question.num_incorrect:
#                     majority_sign = 1
#                 else:
#                     majority_sign = -1
#                 if abs(current_prediction) < current_question_min:
#                     current_prediction = sign(current_prediction)*current_question_min
#                 if sign(current_prediction) != majority_sign:
#                     current_prediction = majority_sign*abs(current_prediction) 
#                 cluster[i].prediction = current_prediction
#                 testExamples[i].prediction = int(ceil(predictions_abs[i]))
        
        for i in range(len(predictions_abs)):
#             current_sign = predictions_binary[i]
            current_sign = sign(predictions_abs[i])
            current_abs = abs(predictions_abs[i])
            if(i < len(cluster)):
                current_question = cluster[i].question
                if current_abs >= current_question.length:
                    current_abs = current_question.length
    #             cluster[i].prediction = int(ceil(random.choice([1, -1])*current_abs))
                cluster[i].prediction = int(ceil(current_sign*current_abs))
                clusters_out.append(cluster[i])
            else:
                print "Length of cluster: "+str(len(cluster))+"\n Length of predictions: "+str(len(predictions_abs))+"\nFor range: "+range_string
                break
        
        current_err = self.rootMeanSquaredError(cluster)
        print str("ERROR for cluster "+str(cluster_index)+": "+str(current_err) +"\n"+
                  "Range of cluster: "+range_string+"\n"+
                  "Size of cluster: "+str(len(cluster)))
        err_val.value = float(current_err)
        
#             testExamples[i].prediction = int(ceil(current_sign*current_abs))
#             testExamples[i].prediction = int(ceil(current_sign*average))
    
#     return predictions_abs, predictions_binary

    def producePredictions(self, trainingExamples, testExamples, users, continuous_features_array, binary_features_array, wiki_data, category_dict, average):
        clusters = []
        cluster_ranges = []
        trainingExamples_ranges = []
        if not self.cluster:
            clusters = [testExamples]
            cluster_ranges.append([0, len(testExamples)])
            trainingExamples_ranges = [trainingExamples]
        else:
            answer_ranges = self.cluster_boundaries#[10,50,100]
            last_range = 0
            for num_answered_range in answer_ranges:
                current_cluster = []
                current_training_cluster = []
                for testExample in testExamples:
                    current_user_questions = users[testExample.user].num_questions 
                    if current_user_questions <= num_answered_range and current_user_questions > last_range:
                        current_cluster.append(testExample)
                if self.cluster_training_data:
                    for trainingExample in trainingExamples:
                        current_example_user_questions = users[trainingExample.user].num_questions
                        if current_example_user_questions <= num_answered_range and current_example_user_questions > last_range:
                            current_training_cluster.append(trainingExample)
                    trainingExamples_ranges.append(current_training_cluster)
                clusters.append(current_cluster)
                cluster_ranges.append([last_range, num_answered_range])
                last_range = num_answered_range 
#         if 'kernel' in binary_features:
#             kernel = binary_features['kernel']
#         else:
#             kernel = 'rbf'
#             binary_features['kernel'] = 'rbf'
#             
#         if 'gamma' in binary_features:
#             gamma = float(binary_features['gamma'])
#         else:
#             gamma = 0.0
#             binary_features['gamma'] = str(gamma)
        predictor_processes = []
        clusters_out = {}
        clusters_error = {}
        manager = Manager()
        for cluster_index in range(len(clusters)):
            high_memory_process = False
            continuous_features = continuous_features_array[cluster_index]
            if 'continuous_classifier' in continuous_features:
                classifier_type = continuous_features['continuous_classifier']
            else:
                classifier_type = ""
            if classifier_type == 'gaussian_process' or classifier_type == 'decision_tree_regressor' or classifier_type == 'kernel_ridge' or classifier_type == 'ensemble_randomforest':
                high_memory_process = True
            binary_features = binary_features_array[cluster_index]
            cluster = clusters[cluster_index]
            if self.cluster_training_data:
                trainingExamplesCluster = trainingExamples_ranges[cluster_index]
            else:
                trainingExamplesCluster = trainingExamples
            cluster_out = manager.list()
            if len(cluster) == 0 or cluster_index in self.skip_clusters:
                continue
            err_val = Value(ctypes.c_float, 0.0)
            clusters_error[cluster_index] = err_val
            clusters_out[cluster_index] = cluster_out
            current_process = Process(target=self.producePredictionsProcess, 
                                      args=(cluster, cluster_index, cluster_ranges, continuous_features, 
                                            binary_features, category_dict, users, wiki_data, 
                                            trainingExamplesCluster, cluster_out, err_val))
            if high_memory_process:
                for process in predictor_processes:
                    process.join()
                    predictor_processes.remove(process)
                print "Starting high memory process"
            predictor_processes.append(current_process)
            current_process.start()
            
        for process in predictor_processes:
            process.join()
            
        for cluster_index in range(len(clusters)):
            if cluster_index in clusters_out:
                orig_cluster = clusters[cluster_index]
                out_cluster = clusters_out[cluster_index]
                for ex_index in range(len(orig_cluster)):
#                     print ex_index
                    orig_cluster[ex_index].prediction = out_cluster[ex_index].prediction
        return clusters_error, cluster_ranges
            
        
        
    def recordCrossValidationResults(self, err, recordFile, features_abs_used, features_sign_used, ranges_string):
        if os.path.exists(recordFile) and os.path.isfile(recordFile):
            num_lines = sum(1 for line in open(recordFile))
        else:
            num_lines = 0
        recordFile = open(recordFile, 'a')
        writer = DictWriter(recordFile, fieldnames=["Error", "Time", "Range Errors", "Features"])
        if num_lines == 0:
            writer.writeheader()
        
        ts = time.time()
        timestamp = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    #     recordFile.write('\nError:  '+str(err)+' Timestamp: '+str(timestamp)+ ' Features used: '+str(features_used))
        writer.writerow({'Error':err, 'Time':timestamp, 'Range Errors':ranges_string, 'Features':"Continuous:"+str(features_abs_used)+" Binary:"+str(features_sign_used)})
        recordFile.flush()
        recordFile.close()
    
        
    def load_wiki_data(self, wiki_file):
        if os.path.exists(wiki_file) and os.path.isfile(wiki_file):
            infile = open(wiki_file, 'rb')
            print "Loading Wikipedia data"
            wiki_data = pickle.load(infile)
            infile.close()
            return wiki_data
        else:
            if not os.path.exists(wiki_file):
                print "Wikipedia data file not found"
            if os.path.exists(wiki_file) and not os.path.isfile(wiki_file):
                print "Wikipedia file exists but is not a file"
            return {}  
       
    def store_wiki_features(self, wiki_file, wiki_data):
        outfile = open(wiki_file, 'wb')
        print "Storing Wikipedia data"
        pickle.dump(wiki_data, outfile)
        outfile.flush()
        outfile.close()

    def create_example_from_csv(self, users, row, questions, categories_dict, test=False):
        current_example = Example()
        current_example.id = row['id']
        q_id = int(row['question'])
        current_example.question = questions[q_id]
        current_example.user = int(row['user'])
        if 'position' in row:
            current_example.observation = int(float(row['position']))
        
        if not test:
            position = float(row['position'])
        else:
            position = 0
        
        u_id = int(row['user'])
        if u_id not in users:
            current_user = User(u_id)
            users[u_id] = current_user
            
        else:
            current_user = users[u_id]
            
        if not test: 
            if position > 0:
                correct = True
            else:
                correct = False
            answer = row['answer']
            current_category = questions[q_id].category
#             print position
            current_user.add_question(q_id, correct, position, answer, current_category)
            
            current_example.answer = answer
            current_example.question.add_question_occurence(position)
            current_example.previous_prediction = position
            
            
            categories_dict[current_category].add_occurrence(current_user, position)
            
        return current_example
    
    def create_examples(self, users, fileName, categories_dict, questions_dict, nTrainingSets=-1, generate_test=False, all_test=False, limit=-1):
        fin = open(fileName, 'rt')
        reader = csv.DictReader(fin)
        
        train_examples = []
        test_examples = []
        
        rowIndex = 0
        nTrainingSets = self.args.local_selection
        total = 0.0
        count = 0.0
        for row in reader:
            if limit > 0 and rowIndex >= limit:
                break
            if all_test or generate_test and nTrainingSets > 0 and rowIndex % nTrainingSets == 0:
                current_example = self.create_example_from_csv(users, row, questions_dict, categories_dict, test=True)
                test_examples.append(current_example)
            else:
                total += float(row['position'])
                count += 1
                current_example = self.create_example_from_csv(users, row, questions_dict, categories_dict)
                train_examples.append(current_example)
            rowIndex += 1
        
        fin.close()
        
        if generate_test:
            average = total/count
            return train_examples, test_examples, average
        elif all_test:
            return test_examples
        else:
            return train_examples

         

        
    def run(self):
        usingWikipediaFeatures = False
        for features in self.position_features:
            if features['wiki_answer']:
                usingWikipediaFeatures = True
                break
        for features in self.correctness_features:
            if features['wiki_answer'] or usingWikipediaFeatures:
                usingWikipediaFeatures = True
                break
#         usingWikipediaFeatures = self.position_features['wiki_answer'] or self.correctness_features['wiki_answer']
    
        if usingWikipediaFeatures and not self.args.regenerate_wiki:
            wiki_data_file = self.args.wiki_file
            wiki_data = self.load_wiki_data(wiki_data_file)
            original_wiki_length = len(wiki_data)
        else:
            wiki_data = {}
            original_wiki_length = 0
        
        questionFile = "questions_processed.csv"
        fin = open(questionFile, 'rt')
        reader = csv.DictReader(fin)#, ['id', 'answer', 'type', 'category', 'question', 'keywords'])
        questions = dict()
        categories = dict()
        for row in reader:
            key_dict = eval(row['keywords'])
            question_list = eval(row['question'])
            category = row['category']
            question = Question(question_list, row['category'], key_dict, row['answer'], row['type'], row['id'])
            if row['category'] not in categories:
                current_category = Category(category)
                categories[category] = current_category
            else:
                current_category = categories[category]
            current_category.add_question(question.q_id)
            questions[int(row['id'])] = question
        fin.close()
        users = {}
        # Read training examples
        trainingFile = "train.csv"
        
        trainingExamples, testExamples, average_abs = self.create_examples(users, trainingFile, categories, questions, nTrainingSets=self.args.local_selection, generate_test=True, limit=self.args.limit)
        
        
        print "\nRead data"
        
        if self.args.local:
            errors = []
                    
            process_errors, process_ranges = self.producePredictions(trainingExamples, testExamples, users, self.position_features, self.correctness_features, wiki_data, categories, average_abs)
            
            range_str_array = []
            
            for error_index in range(len(process_errors)):
                interval = str(process_ranges[error_index][0])+" - "+str(process_ranges[error_index][1])+" : "
                range_str_array.append(interval+str(process_errors[error_index].value))
            
            print "\nFinished prediction"
            
            err = self.rootMeanSquaredError(testExamples)
            
            self.recordCrossValidationResults(err, 'records.csv', self.position_features, self.correctness_features, "|".join(range_str_array))
            
            self.recordErrors("errors.csv", testExamples, users, categories)
            
            print "CROSS-VALIDATION RESULTS"
            print "ERROR: ", err#np.mean(errors)
    
        if self.args.predict:
            # Read test file
            print "\nWriting predictions file"
            testFile = "test.csv"
            
            testExamples = self.create_examples(users, testFile, categories, questions, all_test=True)
            
            trainingExamples = self.create_examples(users, trainingFile, categories, questions)
            
            # Generate predictions
            self.producePredictions(trainingExamples, testExamples, users, self.position_features, self.correctness_features, wiki_data, categories, average_abs)
         
            # Produce submission file
            submissionFile = "submission.csv"
            fout = open(submissionFile, 'w')
            writer = csv.writer(fout)
            writer.writerow(("id","position"))
            for ex in testExamples:
                writer.writerow((ex.id, ex.prediction))
            fout.close()
            print "\nPredictions file written"
            
        if usingWikipediaFeatures:
            wiki_data_file = self.args.wiki_file
            if self.args.regenerate_wiki or len(wiki_data) > 0 and original_wiki_length != len(wiki_data):
                self.store_wiki_features(wiki_data_file, wiki_data)