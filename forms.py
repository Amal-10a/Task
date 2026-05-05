from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, SelectField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp, Optional, NumberRange, Email

class AnnouncementForm(FlaskForm):
    title = StringField('العنوان', validators=[
        DataRequired(message='العنوان مطلوب'),
        Length(min=3, max=80, message='العنوان يجب أن يكون 3-80 حرف')
    ])
    content = TextAreaField('المحتوى', validators=[
        DataRequired(message='المحتوى مطلوب'),
        Length(min=10, max=1000, message='المحتوى يجب أن يكون 10-1000 حرف')
    ])
    submit = SubmitField('حفظ')

# Removed unused EmployeeForm, LoginForm, TaskForm - use inline validation for simplicity
